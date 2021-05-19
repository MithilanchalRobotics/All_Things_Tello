"""
Project : Make the best of DJI Tello.
Start Date : 05/10/2021
Author : Sarvesh Thakur
"""
import cv2
import time
import math
from queue import Queue
import keyboard
from djitellopy import Tello


def printHelper():
    print("""
            Welcome to Flight Control Management System for Tello EDU
            
            For Manual Control, following controls are supported:
                1. 'S' : Start Tello, take off
                2. 'Q' : Quit Streaming, land
                3. Move in plane: 
                                W
                            A       D
                                Z
                4. Yaw Control:
                    Right arrow -> : Clockwise
                    Left arrow <- : Anti-Clockwise
                5. Height Control:
                    Up Arrow ^ : Increase
                    Down Arrow v : Decrease
                    
                    --- Moving in Vertical plane and rotation about Vertical axes ---
                                ^
                            <       >
                                v          
                6. 'P' : Take snapshot
                7. 'O'(alphabet O as in Owl) : Capture 360deg panorama
                8. 'C' : Capture 180deg panorama
        
            Thank you! Fly Safe!
    """)


class FlightControl:
    """
    Class is responsible for initialization, in-flight and post-flight control.
    Currently it supports only single tello functions
    """

    def __init__(self):
        printHelper()
        self.tello = None
        self.frameObject = None
        self.frame = None
        self.outputDir = "output\\"
        self.FOV = 30  # assuming 75 degrees FOV of Tello EDU

        # To avoid multiple snaps when requested only once (It seems key pressed time is longer than the processing
        # time of while loop asking for user input Hence user's one time key press is actually processed more than
        # once)
        self.snapOrdered = False
        self.videoOrdered = False  # Implemented after Panorama mode works
        self.videoOutputName = None  # Implemented after Panorama mode works

        # Keep track of actions requested by the user
        self.ActionStack = []
        self.timeDifference = 0.2  # time between consecutive actions be greater than 100ms

        # Panorama
        self.panoramaOrdered = False
        self.panoramaDeg = 0
        self.totalPanoramaCaptures = 0
        self.panoramaQueue = Queue(maxsize=0)  # Stores all the frames required to create a panorama

        self.HeavyMode = False  # This mode is entered when a event such as panorama capture or reconstruction is
        # entered. Allows bypassing modes other than quit(Q).

    def init(self):
        self.tello = Tello()
        self.tello.connect()
        self.setAllVelocity(0)
        self.tello.streamon()
        self.tello.get_battery()

    def deinit(self):
        self.tello.streamoff()
        self.tello.end()
        time.sleep(1.0)  # Let it cool down

    def setAllVelocity(self, val):
        self.tello.front_back_velocity = 0
        self.tello.left_right_velocity = 0
        self.tello.up_down_velocity = 0
        self.tello.yaw_velocity = 0
        self.tello.speed = 0

    def getFrame(self):
        _ = self._readFrame()
        return self._getFrame()

    def _readFrame(self):
        self.frameObject = self.tello.get_frame_read()
        return self.frameObject

    def _getFrame(self):
        self.frame = self.frameObject.frame
        return self.frame

    def getKeyboardInput(self):
        commands = ["up", "down", "a", "d", "w", "z", "left", "right", "p", "c"]
        # wait key command should be given only single time, otherwise delay!
        if cv2.waitKey(1) & keyboard.is_pressed("s"):
            self.updateActionTrack("s")  # Update action track
            return "s"
        else:
            for key in commands:
                if keyboard.is_pressed(key):
                    self.updateActionTrack(key)  # Update action track
                    return key
            return None

    def updateActionTrack(self, key):
        if key is not None:
            self.ActionStack.append((key, time.time()))
        return True  # figure out use later

    def calculateAction(self, command):
        valid_command = self.checkValidCommand(command)

        if valid_command:
            if command is None:
                self.setAllVelocity(0)
            elif command == "s":
                self.tello.takeoff()
            elif command == "up":
                self.tello.up_down_velocity = 60
            elif command == "down":
                self.tello.up_down_velocity = -60
            elif command == "left":
                self.tello.yaw_velocity = -60
            elif command == "right":
                self.tello.yaw_velocity = 60
            elif command == "a":
                self.tello.left_right_velocity = -60
            elif command == "d":
                self.tello.left_right_velocity = 60
            elif command == "w":
                self.tello.front_back_velocity = 60
            elif command == "z":
                self.tello.front_back_velocity = -60
            elif command == "p":
                self.snapOrdered = True
                self.takeSnap()
            elif command == "c":
                self.capturePanorama("C")

    def checkValidCommand(self, command):
        if command is None:
            return True
        # Get two recent commands requested and compare time.
        if len(self.ActionStack) >= 2:
            last = self.ActionStack[-1]
            second_last = self.ActionStack[-2]
            diff = last[1] - second_last[1]
            # print(last, second_last, diff, self.timeDifference)
            if (last[0] == second_last[0]) & (diff < self.timeDifference):
                return False
        return True

    def capturePanorama(self, degree="C"):

        self.panoramaOrdered = True
        self.HeavyMode = True

        if degree == "C":
            self.panoramaDeg = 180
        elif degree == "O":
            self.panoramaDeg = 360

        self.totalPanoramaCaptures = max(math.floor(self.panoramaDeg / self.FOV), math.floor(self.panoramaDeg / self.FOV) + 1)
        deg_to_rotate = self.FOV
        self.capturePanorama_(deg_to_rotate, self.totalPanoramaCaptures)

        self.totalPanoramaCaptures = 0
        self.HeavyMode = False
        self.panoramaOrdered = False

    def capturePanorama_(self, deg_to_rotate, n, folder="panorama"):
        """
        Rotate at deg_to_rotate degrees each time and capture n images.
        :param folder: Name of the folder for output
        :param deg_to_rotate: rotation in degree
        :param n : total images to capture
        :return: void (updates queue with panorama images)
        """
        print("[capturePanorama_] : #Photos : {} , Degree : {} ".format(n, deg_to_rotate))
        # capture, rotate and capture
        self.takeSnap_("panoramas")
        time.sleep(0.2)

        action_taken = True
        for i in range(n-1):
            self.rotate(deg_to_rotate)
            self.takeSnap_("panoramas")

        action_taken = self.rotate(-(n - 1) * deg_to_rotate)  # Get back to the original orientation
        return action_taken


    def rotate(self, degrees):
        print("[FlightControl] : [rotate] : To rotate by {} degrees".format(degrees))
        self.setAllVelocity(0)
        time.sleep(0.1)

        if degrees >= 0:
            result = self.tello.rotate_counter_clockwise(degrees)
            time.sleep(3)
        else:
            result = self.tello.rotate_clockwise(-1 * degrees)
            time.sleep(3)

        print("[FlightControl] : [rotate] : Rotate by {} degrees : {}".format(degrees, result))
        return result

    def takeSnap(self, folderName="snaps"):
        if self.snapOrdered:
            t = time.localtime()
            name = self.outputDir + folderName + "\\" + str(t) + ".jpg"
            cv2.imwrite(name, self.frame)
            print("[FlightControl]: [takeSnap]: Snap saved at {}".format(name))
            self.snapOrdered = False

    # called by methods like panorama, reconstruction etc.
    def takeSnap_(self, folderName="panoramas"):
        frame = self.getFrame()
        t = time.localtime()
        name = self.outputDir + folderName + "\\" + str(t) + ".jpg"
        cv2.imwrite(name, self.frame)
        print("[FlightControl]: [takeSnap]: Snap saved at {}".format(name))
        time.sleep(1)

    def takeAction(self, land=False):
        if not land:
            if not self.HeavyMode:  # If already in a heavy mode, let it complete!
                self.tello.send_rc_control(self.tello.left_right_velocity, \
                                           self.tello.front_back_velocity, \
                                           self.tello.up_down_velocity, \
                                           self.tello.yaw_velocity)
        else:
            self.setAllVelocity(0)
            self.tello.land()
            time.sleep(1)
