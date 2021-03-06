# S2C

A secret video chat "in terminal" using PGP encryptions and AES encryptions.
No Browser needed !

## Features

- Video + Audio Chat in terminal

### Requirements

- Python (3.x is recommended)
- Pip3
- PyAudio

## How to use

### Installation

Install bindings librairies for pyaudio !
- On linux/Mac : `sudo apt install -y portaudio19-dev` and `sudo apt install -y pyaudio`


Because it's a pip package, you need to install it using pypi !
```shell
pip install s2c
```

### Manual

#### Client 

The manual of s2c :
```shell
usage: s2c [-h] [-s SESSION_ID] [-c CLIENT_ID] [-k KEY] [-i IP] [-p PORT]

optional arguments:
  -h, --help            show this help message and exit
  -s SESSION_ID, --session_id SESSION_ID
                        The sesion_id, if noting is provide,it will generate
                        for you
  -c CLIENT_ID, --client_id CLIENT_ID
                        Your id or name in the session, if noting is
                        provide,it will generate for you
  -k KEY, --key KEY     To provide the custom key for the AES encryption
  -i IP, --ip IP        The host of the server where websockets will transits
  -p PORT, --port PORT  The port of the host
```

For example : `$s2c -s 1 -c 1 -i 127.0.0.1 -p 1122`
Will connect you to the server '127.0.0.1:1122' in the session '1', your id is '1' !

#### Server

NB : At this step, the server should be running on ip : 127.0.0.1 and on port 1122, don't forget to allow the port using ufw (on linux)

To run the server :
```
s2c_server -p 1122
```

## From sources

### How to install

Install bindings librairies for pyaudio !
- On linux/Mac : `sudo apt install -y portaudio19-dev` and `sudo apt install -y pyaudio`

Clone and set the virtualenvironment :
```shell
# We clone the repository
git clone https://github.com/sanix-darker/s2c

# We Set the virtualenv
virtualenv -p python3 venv
source venv/bin/activate

# We install requirements
pip install -r requirements
```

### How to launch

#### The server

The server take only one parameter, the port, where it's going to run !
```shell
python3 -m server.main -h

usage: main.py [-h] [-p PORT]

optional arguments:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  The port where the server will be running
```

#### The Client

Just as the section Manual under How to use, you just have to replace `s2c` by `python3 -m app.main`

## About

- [d4rk3r](https://github,com/sanix-darker)


