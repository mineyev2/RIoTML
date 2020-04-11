import socket, select, string, sys

# import the necessary packages
from collections import deque
from imutils.video import VideoStream
import numpy as np
import argparse
import cv2
import imutils
import time
import pantilthat

import threading
import multiprocessing
import time

client_input = "turning on"

def wait_for_input():
    client_input = sys.stdin.readline()

#Helper function (formatting)
def display() :
	you="\33[33m\33[1m"+" You: "+"\33[0m"
	sys.stdout.write(you)
	sys.stdout.flush()

def main():
    found = False
    global client_input
    # construct the argument parse and parse the arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("-b", "--buffer", type=int, default=64,
                    help="max buffer size")
    args = vars(ap.parse_args())

    # define the lower and upper boundaries of the "green"
    # ball in the HSV color space, then initialize the
    # list of tracked points
    greenLower = (0, 150, 150)
    greenUpper = (64, 255, 255)
    pts = deque(maxlen=args["buffer"])

    vs = VideoStream(src=0).start()

    pantilthat.pan(0)
    pantilthat.tilt(0)

    # allow the camera or video file to warm up
    time.sleep(2.0)

    print("Starting server now")

    host = '192.168.1.78'
    port = 11000

    # asks for user name
    file = open("../number.txt", "r")
    name = file.read()
    file.close()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)

    # connecting host
    try:
        s.connect((host, port))
    except:
        print("\33[31m\33[1m Can't connect to the server \33[0m")
        sys.exit()

    # if connected
    s.send(name.encode('utf-8'))
    display()

    #get_input = threading.Thread(target=wait_for_input())
    #get_input.start()

    while 1:
        socket_list = [s]

        # Get the list of sockets which are readable
        #MAKE SURE TO USE 0 at the end
        #0 means that select will not wait for server messages or sys.stdin to actually have an output. Otherwise the while loop gets blocked here and the ball_tracking section will not run.
        rList, wList, error_list = select.select(socket_list, [], [], 0)

        for sock in rList:
            # incoming message from server
            if sock == s:
                data = sock.recv(4096).decode()
                if not data:
                    print('\33[31m\33[1m \rDISCONNECTED!!\n \33[0m')
                    sys.exit()
                else:
                    sys.stdout.write(data)
                    display()
        #print("running ball tracking")

        # grab the current frame
        frame = vs.read()

        # handle the frame from VideoCapture or VideoStream
        frame = frame[1] if args.get("video", False) else frame

        # resize the frame, blur it, and convert it to the HSV
        # color space
        frame = imutils.resize(frame, width=600)
        blurred = cv2.GaussianBlur(frame, (11, 11), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # construct a mask for the color "yellow", then perform
        # a series of dilations and erosions to remove any small
        # blobs left in the mask
        mask = cv2.inRange(hsv, greenLower, greenUpper)
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)

        # find contours in the mask and initialize the current
        # (x, y) center of the ball
        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        center = None

        # only proceed if at least one contour was found
        if len(cnts) > 0:
            if(not found):
                msg='0'
                #print(msg.encode('utf-8'))
                s.send(msg.encode('utf-8'))
                #display()
                found = True
            # find the largest contour in the mask, then use
            # it to compute the minimum enclosing circle and
            # centroid
            c = max(cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
            #need to set bounds for the values here eventually so it doesn't crash when the desired angle is over 90 or under -90
            pan = pantilthat.get_pan() + (center[0] - 300) / 50
            tilt = pantilthat.get_tilt() - (center[1] - 240) / 50

            # if past the tick, send message to other pis so they can start tracking too

            if(pan > 70):
                msg = '1,' + str(tilt)
                s.send(msg.encode('utf-8')
            if(pan < -70):
                msg = '2,' + str(tilt)
            if(pan > 90):
                pantilthat.pan(90)
            elif(pan < -90):
                pantilthat.pan(-90)
            else:
                pantilthat.pan(pan)

            if(tilt > 90):
                pantilthat.tilt(90)
            elif(tilt < -90):
                pantilthat.tilt(-90)
            else:
                pantilthat.tilt(tilt)


            #pantilthat.pan(pantilthat.get_pan() + (center[0] - 300) / 50)
            #pantilthat.tilt(pantilthat.get_tilt() - (center[1] - 240) / 50)
        else:
            found = False


        # update the points queue
        pts.appendleft(center)
if __name__ == "__main__":
    main()
