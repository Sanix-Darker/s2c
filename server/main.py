# The server part
# The place where i will forward the whole traffic
# By d4rk3r
import argparse
import socket
import threading
import json



class Server:
    def __init__(self, port):
            self.rooms = {}
            self.ip = socket.gethostbyname(socket.gethostname())
            while True:
                try:
                    self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.s.bind((self.ip, self.port))

                    break
                except:
                    print("[x] Couldn't bind to that port []".format(str(self.port)))

            self.accept_connections()

    def accept_connections(self):

        self.s.listen(100)

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
        if json_data["i"] not in self.rooms["s"]
            self.rooms[json_data["s"]][json_data["i"]] = {"c": sock}

    def broadcast(self, sock, json_data):
        """
        In this method we're going to broadcast the whole thing
        """
        self.save_room_set(sock, json_data)

        # We loop over all clients in the session
        # To send them the flux
        for elt in self.rooms[json_data["s"]]:
            if elt["c"] != self.s and elt["c"] != sock:
                try:
                    elt["c"].send(json_data)
                except:
                    pass

    def handle_client(self, c, addr):
        while True:
            try:
                data = c.recv(3072)
                json_data = json.loads(data.decode())

                # We check first the format
                # i for the id, s for the session,
                # v for the video string and a for the audio chunk
                if all(k in json_data.keys() for k in ["i", "s", "v", "a"]):
                    self.broadcast(c, json_data)
            except socket.error:
                c.close()



if __name__ == "__main__":
    # Initialize the arguments
    prs = argparse.ArgumentParser()
    prs.add_argument('-p', '--port',
            help='The port where the server will be running',
            type=str, default="77223")
    prs = prs.parse_args()

    # We start our server
    server = Server(prs.port)
