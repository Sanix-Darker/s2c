# The server part
# The place where i will forward the whole traffic
# By d4rk3r
import argparse
import socket
import threading
import json
import time
from app.utils.helpers import get_trace



class Server:
    def __init__(self, port):
            self.rooms = {}
            self.ip = '0.0.0.0'
            self.port = port
            while True:
                try:
                    self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.s.bind((self.ip, self.port))

                    self.s.listen()

                    break
                except:
                    print("[x] Couldn't bind to that port {}".format(str(self.port)))
                    time.sleep(1)

            self.accept_connections()

    def accept_connections(self):

        print('[-] Running on IP: ' + self.ip)
        print('[-] Running on port: ' + str(self.port))

        while True:
            c, addr = self.s.accept()
            # Here we're going to handle clients with threads
            threading.Thread(target=self.handle_client,args=(c,addr,)).start()

    def save_room_set(self, sock, json_data):
        """
        This method will create a session group and add the current id
        in it if everything is not set for that client

        """
        # if the session doesn't exist we create it
        if json_data["s"] not in self.rooms:
            self.rooms[json_data["s"]] = {}

        # if the current id not in the target session, we add it
        if json_data["i"] not in  self.rooms[json_data["s"]]:
            self.rooms[json_data["s"]][json_data["i"]] = {}
            self.rooms[json_data["s"]][json_data["i"]]["c"] = sock

    def broadcast(self, sock, json_data):
        """
        In this method we're going to broadcast the whole thing
        """
        self.save_room_set(sock, json_data)

        # We loop over all clients in the session
        # To send them the flux
        for elt in self.rooms[json_data["s"]]:
            client = self.rooms[json_data["s"]][elt]["c"]
            if client != self.s and client != sock:
                try:
                    client.send(bytes(json.dumps(json_data), encoding="utf-8"))
                except Exception as es:
                    get_trace()

    def handle_client(self, c, addr):
        while True:
            try:
                try:
                    data = c.recv(5120)
                    if len(data.decode("utf-8")) > 30:
                        json_data = json.loads(data.decode())
                        print("-"*80)
                        print("json_data: ", json_data)

                        # We check first the format
                        # i for the id, s for the session,
                        # v for the video string and a for the audio chunk
                        if all(k in json_data.keys() for k in ["i", "s", "a", "v"]):
                            self.broadcast(c, json_data)
                        else:
                            print("[x] Incomplete sequence !")
                except json.decoder.JSONDecodeError as es:
                   pass
            except socket.error:
                c.close()



if __name__ == "__main__":
    # Initialize the arguments
    prs = argparse.ArgumentParser()
    prs.add_argument('-p', '--port',
            help='The port where the server will be running',
            type=int, default=1122)
    prs = prs.parse_args()

    # We start our server
    server = Server(prs.port)

