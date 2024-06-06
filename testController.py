"""A simple program to test controllers"""
from cmu_graphics import *
import joystick

def onAppStart(app):
    app.text = f"Joystick: button pressed:"

def onJoyPress(app, button, joystick):
    app.text = f"Joystick: {joystick} button pressed: {button}"

def redrawAll(app):
    drawLabel(app.text, app.width//2, app.height//2, size=30)

runApp(width=800, height=600)
