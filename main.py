"""
Author : Sarvesh Thakur
"""


from FlightControl import *


if __name__ == "__main__":
    fc = FlightControl()

    fc.init()

    while True:
        frame = fc.getFrame()
        cv2.imshow("I am DJI Tello EDU", frame)

        if cv2.waitKey(1) and keyboard.is_pressed('q'):
            fc.takeAction(land=True)
            break
        else:
            key = fc.getKeyboardInput()
            fc.calculateAction(key)
            fc.takeAction()


    fc.deinit()
