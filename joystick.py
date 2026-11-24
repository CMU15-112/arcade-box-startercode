import os

from cmu_graphics import almostEqual, onStepEvent

try:
    # cmu_graphics 1.x runs on pygame and passes us its events
    from cmu_graphics import pygameEvent
except ImportError:
    # cmu_graphics 3.x doesn't use pygame, so we read the joystick events ourselves
    # in handleOnStepEvent.
    pygameEvent = None

try:
    try:
        # Use this to import pygame if cmu_graphics 1.x was installed via zip file
        from cmu_graphics.libs import pygame_loader as pygame
    except ImportError:
        # Otherwise use the normally installed pygame
        os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
        import pygame
except ImportError:
    pygame = None
    print("joystick.py: pygame is not installed, so joystick support is disabled. "
          "(Your program will still run; joystick callbacks just won't be called.)")

if pygame is not None and pygameEvent is None:
    # pygame's event queue needs its display started, so start one of SDL's windowless
    # displays. Not every SDL build has both: the R36S's has only "offscreen".
    os.environ.setdefault('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')
    _drivers = ['dummy', 'offscreen']
    if os.environ.get('SDL_VIDEODRIVER'):
        _drivers.insert(0, os.environ['SDL_VIDEODRIVER'])
    for _driver in _drivers:
        os.environ['SDL_VIDEODRIVER'] = _driver
        try:
            pygame.display.init()
            pygame.joystick.init()
            break
        except pygame.error as _e:
            if _driver == _drivers[-1]:
                pygame = None
                print(f"joystick.py: couldn't start pygame ({_e}), so joystick support "
                      "is disabled. (Your program will still run.)")

_allJoyButtonsDown = dict()
_allDigitalJoyAxisDown = dict()
_lastJoyAxis = dict()
_joysticks = dict()

# If this user releases all joystick presses, trigger
# onDigitalJoyAxis one more time with an empty list
# so that we can tell it was released.
_digitalJoyAxisSendEmpty = dict()


def handlePygameEvent(event, callUserFn, app):
    if event.type == pygame.JOYDEVICEADDED:
        joy = pygame.joystick.Joystick(event.device_index)
        _joysticks[joy.get_instance_id()] = joy
        _allJoyButtonsDown[joy.get_instance_id()] = set()
        _allDigitalJoyAxisDown[joy.get_instance_id()] = set()
        _digitalJoyAxisSendEmpty[joy.get_instance_id()] = False
        joy.rumble(0, 0.7, 500)  # Rumble if it can and is connected
    elif event.type == pygame.JOYDEVICEREMOVED:
        del _joysticks[event.instance_id]
        key = f"J{event.instance_id}H"
        if key in _lastJoyAxis:
            del _lastJoyAxis[key]
        del _allJoyButtonsDown[event.instance_id]
        del _allDigitalJoyAxisDown[event.instance_id]
    elif event.type == pygame.JOYBUTTONDOWN:
        handleJoyPress(str(event.button), event.instance_id, callUserFn)
    elif event.type == pygame.JOYBUTTONUP:
        handleJoyRelease(str(event.button), event.instance_id, callUserFn)
    elif event.type == pygame.JOYHATMOTION:
        handleJoyHat(event.value, event.instance_id, callUserFn)
    elif event.type == pygame.JOYAXISMOTION:
        handleDigitalJoyAxis(event.value, event.axis, event.instance_id)
        callUserFn('onJoyAxis', (event.value, event.axis, event.instance_id))


if pygame is not None and pygameEvent is not None:
    pygameEvent.connect(handlePygameEvent)


# The R36S launcher sets CMU_R36S_JOY=1 to renumber the R36S gamepad like the CMU arcade
# box (see STUDENT_GUIDE.md). a/b/x/y, L1/R1 and L2/R2 already match; Select/Start move
# to 8/9 like the arcade box; L3/R3 take 10/11. The D-pad becomes axes 0/1, like the
# left stick. Pressing Select and Start together quits.
R36S = pygame is not None and os.environ.get('CMU_R36S_JOY') == '1'
R36S_BUTTONS = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 12: 8, 13: 9, 14: 10, 15: 11}
R36S_DPAD = {8: (1, -1), 9: (1, 1), 10: (0, -1), 11: (0, 1)}  # raw button -> (axis, direction)
R36S_SELECT, R36S_START = 12, 13
_r36sHeld = set()


def translateR36S(event, app):
    """Returns the arcade box version of an R36S gamepad event, or None to drop it."""
    if event.type not in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
        return event
    b = event.button
    if event.type == pygame.JOYBUTTONDOWN:
        _r36sHeld.add(b)
    else:
        _r36sHeld.discard(b)
    if R36S_SELECT in _r36sHeld and R36S_START in _r36sHeld:
        app.quit()
        return None
    if b in R36S_DPAD:
        axis = R36S_DPAD[b][0]
        neg, pos = (10, 11) if axis == 0 else (8, 9)
        value = float((pos in _r36sHeld) - (neg in _r36sHeld))
        return pygame.event.Event(pygame.JOYAXISMOTION, instance_id=event.instance_id,
                                  axis=axis, value=value)
    if b in R36S_BUTTONS:
        return pygame.event.Event(event.type, instance_id=event.instance_id,
                                  button=R36S_BUTTONS[b])
    return event


def readJoyEvents(callUserFn, app):
    for event in pygame.event.get():
        if R36S:
            event = translateR36S(event, app)
        if event is not None:
            handlePygameEvent(event, callUserFn, app)


def handleOnStepEvent(callUserFn, app):
    if pygameEvent is None:
        readJoyEvents(callUserFn, app)
    for joystick in _allJoyButtonsDown:
        if len(_allJoyButtonsDown[joystick]) > 0:
            callUserFn('onJoyButtonHold', (list(_allJoyButtonsDown[joystick]), joystick))
    for joystick in _allDigitalJoyAxisDown:
        if len(_allDigitalJoyAxisDown[joystick]) > 0:
            callUserFn('onDigitalJoyAxis', (list(_allDigitalJoyAxisDown[joystick]), joystick))
            _digitalJoyAxisSendEmpty[joystick] = True
        elif _digitalJoyAxisSendEmpty[joystick]:
            callUserFn('onDigitalJoyAxis', (list(_allDigitalJoyAxisDown[joystick]), joystick))
            _digitalJoyAxisSendEmpty[joystick] = False

if pygame is not None:
    onStepEvent.connect(handleOnStepEvent)


def handleJoyPress(button, joystick, callUserFn):
    _allJoyButtonsDown[joystick].add(button)
    callUserFn('onJoyPress', (button, joystick))


def handleJoyRelease(button, joystick, callUserFn):
    if button in _allJoyButtonsDown[joystick]: _allJoyButtonsDown[joystick].remove(button)
    callUserFn('onJoyRelease', (button, joystick))


def handleDigitalJoyAxisPress(value, axis, joystick):
    _allDigitalJoyAxisDown[joystick].add((axis, value))


def handleDigitalJoyAxisRelease(value, axis, joystick):
    if (axis, value) in _allDigitalJoyAxisDown[joystick]: _allDigitalJoyAxisDown[joystick].remove(
        (axis, value))


# Hats are just DPADs, so we'll handle them like buttons
def handleJoyHat(values, joystick, callUserFn):
    # We will index the _lastJoyAxis dict using the joystick and H for hat
    key = f"J{joystick}H"
    prev = _lastJoyAxis.get(key, (0, 0))

    # Only signal a button press if it is newly pressed.
    # You can get (0,1) followed by (1,1), meaning one of the buttons stayed pressed.
    if values[1] == 1 and prev[1] != 1:
        handleJoyPress("H0", joystick, callUserFn)
    elif values[1] == -1 and prev[1] != -1:
        handleJoyPress("H2", joystick, callUserFn)

    if values[1] == 0 and prev[1] == 1:
        handleJoyRelease("H0", joystick, callUserFn)
    elif values[1] == 0 and prev[1] == -1:
        handleJoyRelease("H2", joystick, callUserFn)

    if values[0] == 1 and prev[0] != 1:
        handleJoyPress("H1", joystick, callUserFn)
    elif values[0] == -1 and prev[0] != -1:
        handleJoyPress("H3", joystick, callUserFn)

    if values[0] == 0 and prev[0] == 1:
        handleJoyRelease("H1", joystick, callUserFn)
    elif values[0] == 0 and prev[0] == -1:
        handleJoyRelease("H3", joystick, callUserFn)

    _lastJoyAxis[key] = values


def handleDigitalJoyAxis(value, axis, joystick):
    # We are going to treat this as a digital, which many are.
    if almostEqual(value, 0, 0.5):
        value = 0
    elif almostEqual(value, 1, 0.5):
        value = 1
    elif almostEqual(value, -1, 0.5):
        value = -1
    else:
        return

    # We will index the _lastJoyAxis dict using the joystick and axis
    key = f"J{joystick}A{axis}"
    prev = _lastJoyAxis.get(key, 0)

    # Control stick was pushed in a direction
    if value != 0 and prev == 0:
        handleDigitalJoyAxisPress(value, axis, joystick)

    # Control stick was released in that direction
    if value == 0 and prev != 0:
        handleDigitalJoyAxisRelease(prev, axis, joystick)

    _lastJoyAxis[key] = value
