# 🚗 Remote Virtual Realistic Driving Simulation
 
A remote driving simulation system that enables users to control a real RC vehicle using a steering wheel controller 
through Unity. The system simulates vehicle dynamics, transmits driving commands to an onboard Raspberry Pi, and streams 
live video from the vehicle back to the operator with real-time fisheye image correction.

## Overview

This project bridges a virtual driving interface with a physical RC vehicle. Users drive the vehicle remotely through 
a Unity application that simulates vehicle dynamics including engine behavior, manual and automatic transmission, 
and braking before transmitting driving commands to a Raspberry Pi mounted on the RC vehicle. 
Driving commands are transmitted to a Raspberry Pi mounted on the RC car, which controls the vehicle in real time.

To provide the driver's perspective, a fisheye camera installed on the vehicle streams live video back to the computer 
via WebRTC. The captured frames are processed using OpenCV to remove lens distortion before being displayed, 
creating a more natural driving experience.

## Features
- 🎮 Remote control of an RC vehicle using a steering wheel controller (Logitech G29)
- 🚗 Vehicle dynamics simulation in Unity
  - Engine simulation
  - 5-Speed Manual Transmission simulation
  - Automatic Transmission simulation
  - Braking system
- 📡 Real-time command transmission from Unity to Raspberry Pi via UDP
- 📷 Live video streaming via WebRTC
- 🔍 Fisheye image undistortion using OpenCV
- ⚡ Low-latency remote driving experience

## System Architecture

Steering Wheel (Logitech G29)
       │
       ▼
Unity (Vehicle Simulation)
       │
       ▼
Command Transmission (via UDP)
       │
       ▼
 Raspberry Pi
       │
       ▼
    Arduino
       │
       ▼
    RC Car

Fisheye Camera
       │
       ▼
    WebRTC
       │
       ▼
    OpenCV
(Image Undistortion)
       │
       ▼
 Unity Display

## Technologies

- Unity
- C#
- Raspberry Pi
- Arduino
- UDP
- WebRTC
- OpenCV

## Responsibilities

This project was developed independently from start to finish, including:

- Vehicle dynamics simulation in Unity
- Engine and transmission implementation
- UDP communication between Unity and Raspberry Pi
- Arduino integration for RC vehicle control
- WebRTC video streaming
- Fisheye image undistortion using OpenCV
- System integration and testing

## Source Code

This repository contains the Raspberry Pi, Arduino, and supporting source code.

The Unity project is not included because its size exceeds GitHub's file size limitations.

You can download the Unity project here:

- Google Drive: [<link>](https://drive.google.com/file/d/1QqNPiqn1Y02AmXDGzFT7EnGI-H-gP6Br/view?usp=sharing)
