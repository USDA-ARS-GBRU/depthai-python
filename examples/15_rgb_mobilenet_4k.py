#!/usr/bin/env python3

from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np

# Get argument first
nnPath = str((Path(__file__).parent / Path('models/mobilenet-ssd_openvino_2021.2_5shave.blob')).resolve().absolute())
if len(sys.argv) > 1:
    nnPath = sys.argv[1]

# Start defining a pipeline
pipeline = dai.Pipeline()

# Define a source - color camera
camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setPreviewSize(300, 300)    # NN input
camRgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_4_K)
camRgb.setInterleaved(False)
camRgb.setPreviewKeepAspectRatio(False)

# Define a neural network that will make predictions based on the source frames
nn = pipeline.create(dai.node.MobileNetDetectionNetwork)
nn.setConfidenceThreshold(0.5)
nn.setBlobPath(nnPath)
nn.setNumInferenceThreads(2)
nn.input.setBlocking(False)
camRgb.preview.link(nn.input)

# Create outputs
xoutVideo = pipeline.create(dai.node.XLinkOut)
xoutVideo.setStreamName("video")
camRgb.video.link(xoutVideo.input)

xoutPreview = pipeline.create(dai.node.XLinkOut)
xoutPreview.setStreamName("preview")
camRgb.preview.link(xoutPreview.input)

nnOut = pipeline.create(dai.node.XLinkOut)
nnOut.setStreamName("nn")
nn.out.link(nnOut.input)

# MobilenetSSD label texts
labelMap = ["background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat", "chair", "cow",
            "diningtable", "dog", "horse", "motorbike", "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"]

# Pipeline defined, now the device is connected to
with dai.Device(pipeline) as device:
    # Start pipeline
    device.startPipeline()
        
    # Output queues will be used to get the frames and nn data from the outputs defined above
    qVideo = device.getOutputQueue(name="video", maxSize=4, blocking=False)
    qPreview = device.getOutputQueue(name="preview", maxSize=4, blocking=False)
    qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)

    previewFrame = None
    videoFrame = None
    detections = []

    # nn data, being the bounding box locations, are in <0..1> range - they need to be normalized with frame width/height
    def frameNorm(frame, bbox):
        normVals = np.full(len(bbox), frame.shape[0])
        normVals[::2] = frame.shape[1]
        return (np.clip(np.array(bbox), 0, 1) * normVals).astype(int)

    def displayFrame(name, frame):
        for detection in detections:
            bbox = frameNorm(frame, (detection.xmin, detection.ymin, detection.xmax, detection.ymax))
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (255, 0, 0), 2)
            cv2.putText(frame, labelMap[detection.label], (bbox[0] + 10, bbox[1] + 20), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
            cv2.putText(frame, f"{int(detection.confidence * 100)}%", (bbox[0] + 10, bbox[1] + 40), cv2.FONT_HERSHEY_TRIPLEX, 0.5, 255)
        cv2.imshow(name, frame)

    cv2.namedWindow("video", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("video", 1280, 720)
    print("Resize video window with mouse drag!")

    while True:
        # instead of get (blocking) used tryGet (nonblocking) which will return the available data or None otherwise
        inVideo = qVideo.tryGet()
        inPreview = qPreview.tryGet()
        inDet = qDet.tryGet()

        if inVideo is not None:
            videoFrame = inVideo.getCvFrame()

        if inPreview is not None:
            previewFrame = inPreview.getCvFrame()

        if inDet is not None:
            detections = inDet.detections

        if videoFrame is not None:
            displayFrame("video", videoFrame)

        if previewFrame is not None:
            displayFrame("preview", previewFrame)

        if cv2.waitKey(1) == ord('q'):
            break
