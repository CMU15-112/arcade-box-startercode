"""A simple demo of using a PS4 controller to move a circle."""
from cmu_graphics import *
import joystick
import sys

class Player(object):
    def __init__(self, cx, cy):
        self.radius = 7
        self.x = cx
        self.y = cy
        self.dx = 3
        self.dy = 3

    def getBigger(self):
        self.radius += 1

    def getSmaller(self):
        self.radius -= 1

    def draw(self):
        drawCircle(self.x, self.y, self.radius)

def onAppStart(app):
    app.player = Player(app.width//2, app.height//2)
    app.text = "Welcome"

def onJoyPress(app, button, joystick):
    """Pressing Triangle and X triggers a size change in the circle"""
    app.text = f"Joystick {joystick} button pressed: {button}"
    if button == "3":
        app.player.getBigger()
    elif button == "0":
        app.player.getSmaller()
    # Make sure we can exit by pressing the "P1" button
    elif button == '5':
        sys.exit(-1)

def onJoyRelease(app, button, joystick):
    """Tells you when a button is released on which joystick"""
    app.text = f"Joystick {joystick} button released: {button}"
    pass

def onJoyButtonHold(app, buttons, joystick):
    """This handles movement from the DPAD on a PS4 controller
    Pushing the DPAD results in buttons H0-H3 being pushed
    Not all operating systems support this properly.
    (Mac, for example, seems to have some trouble.)

    On the arcade box, this isn't used.  (The joystick shows up
    as a digital axis, see below.)
    """
    if 'H0' in buttons:
        app.player.y -= app.player.dy
    elif 'H2' in buttons:
        app.player.y += app.player.dy

    if 'H3' in buttons:
        app.player.x -= app.player.dx
    elif 'H1' in buttons:
        app.player.x += app.player.dx

def onDigitalJoyAxis(app, results, joystick):
    """This handles movement using the left analog stick on a PS4 controller.
    On the arcade box, this is the joystick.
    
    Axis 1 is Up/Down (-1 up, 1 down)
    Axis 0 is Left/Right (-1 left, 1 right)
    So, (1,-1) is up, while (0,1) is right.
    """
    app.text = f"Joystick {joystick} axis being held: {results}"
    if (1, -1) in results:
        app.player.y -= app.player.dy
    elif (1, 1) in results:
        app.player.y += app.player.dy

    if (0, -1) in results:
        app.player.x -= app.player.dx
    elif (0, 1) in results:
        app.player.x += app.player.dx

def redrawAll(app):
    app.player.draw()
    drawLabel(app.text, app.width//2, 75, size=30)

#app.myLabel = Label('Welcome to the Demo', app.width//2, app.height//2, size=30)

runApp(width=800, height=600)