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
recieved_y_axis = -1000.0
found = False
pan_running = False
within_range = False
past_range = False


def wait_for_input():
    client_input = sys.stdin.readline()


# Helper function (formatting)
def display():
    you = "\33[33m\33[1m" + " You: " + "\33[0m"
    sys.stdout.write(you)
    sys.stdout.flush()


def analyze(message, s):
    print('\x1b[4;33;40m' + message + '\x1b[0m')

    messages = message.rstrip().split(',')

    try:
        int(messages[0])
        int(messages[1])
    except:
        # print("unreadable")
        return

    rpi_number = int(messages[0])


    if(int(messages[1]) == 2):
        print("reverting back to original position")
        pan = pantilthat.get_pan()
        tilt = pantilthat.get_tilt()

        while(abs(pan) > 5 and abs(tilt) > 5):
            pan = pantilthat.get_pan()
            tilt = pantilthat.get_tilt()

            if (pan > 0):
                pantilthat.pan(pan - 1)
            else:
                pantilthat.pan(pan + 1)
            if(tilt > 0):
                pantilthat.tilt(tilt - 1)
            else:
                pantilthat.tilt(tilt + 1)
            time.sleep(0.02)
        pantilthat.pan(0)
        pantilthat.tilt(0)
        return

    file = open('../number.txt', 'r')
    number = int(file.read())
    file.close()



    global recieved_y_axis
    global pan_running


    try:
        float(messages[2])
    except:
        return

    direction = int(messages[1])
    y_axis = float(messages[2])

    # checks each kind of message that could be delivered

    # first, checks if message was sent for this pi by seeing if the ball is coming towards it
    if (rpi_number + direction == number):
        recieved_y_axis = y_axis
        if (not pan_running):
            thread = threading.Thread(target=pan_till_detected, args=(direction, s, ))
            thread.start()


def pan_till_detected(direction, s):
    global pan_running
    global found
    global recieved_y_axis
    print("pan till detected is running")
    pan_angle = pantilthat.get_pan()

    turn_amt = 1
    sleep_interval = .07
    while (abs(pan_angle) + turn_amt < 90 and not found):
        pantilthat.pan(pan_angle + (-1 * direction) * turn_amt)
        pantilthat.tilt(recieved_y_axis)
        time.sleep(.07)
        pan_angle = pantilthat.get_pan()

    msg = '3'
    print(msg)
    s.send(msg.encode('utf-8'))

    '''
    if(direction > 0):
        while(pan_angle > -90):
            pan_angle = pantilthat.get_pan()
            pantilthat.pan(pan_angle - 1)
            time.sleep(.07)
    else:
        while(pan_angle < 90):
            pan_angle = pantilthat.get_pan()
            pantilthat.pan(pan_angle + 1)
            time.sleep(.07)
    '''


def main():
    global found
    global client_input
    global within_range
    global past_range
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
    port = 12000

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
    # display()

    # get_input = threading.Thread(target=wait_for_input())
    # get_input.start()

    while 1:
        socket_list = [s]

        # Get the list of sockets which are readable
        # MAKE SURE TO USE 0 at the end
        # 0 means that select will not wait for server messages or sys.stdin to actually have an output. Otherwise the while loop gets blocked here and the ball_tracking section will not run.
        rList, wList, error_list = select.select(socket_list, [], [], 0)

        for sock in rList:
            # incoming message from server
            if sock == s:
                data = sock.recv(4096).decode()
                if not data:
                    print('\33[31m\33[1m \rDISCONNECTED!!\n \33[0m')
                    sys.exit()
                else:
                    # read the data from other pis
                    # sys.stdout.write(data)
                    analyze(data, s)
                    # display()
        # print("running ball tracking")

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
            if (not found):
                msg = '0'
                # print(msg.encode('utf-8'))
                s.send(msg.encode('utf-8'))
                # display()
                found = True
            # find the largest contour in the mask, then use
            # it to compute the minimum enclosing circle and
            # centroid
            c = max(cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
            # need to set bounds for the values here eventually so it doesn't crash when the desired angle is over 90 or under -90
            pan = pantilthat.get_pan() + (center[0] - 300) / 50
            tilt = pantilthat.get_tilt() - (center[1] - 240) / 50

            # if past the tick, send message to other pis so they can start tracking too

            if (pan > 50):
                msg = '1,' + str(tilt)
                print(msg)
                s.send(msg.encode('utf-8'))
                past_range = True
            elif (pan < -50):
                msg = '-1,' + str(tilt)
                print(msg)
                s.send(msg.encode('utf-8'))
                past_range = True
            else:
                if(past_range):
                    print("came back to range")
                    msg = '2'
                    print(msg)
                    s.send(msg.encode('utf-8'))
                    #within_range = False
                    past_range = False
            if (pan > 90):
                pantilthat.pan(90)
            elif (pan < -90):
                pantilthat.pan(-90)
            else:
                pantilthat.pan(pan)

            if (tilt > 90):
                pantilthat.tilt(90)
            elif (tilt < -90):
                pantilthat.tilt(-90)
            else:
                pantilthat.tilt(tilt)

            # pantilthat.pan(pantilthat.get_pan() + (center[0] - 300) / 50)
            # pantilthat.tilt(pantilthat.get_tilt() - (center[1] - 240) / 50)
        else:
            # if(
            found = False

        # update the points queue
        pts.appendleft(center)


if __name__ == "__main__":
    main()
