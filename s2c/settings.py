from hashlib import md5
import time
import numpy as np



# Standard loopback interface address (localhost)
HOST = '127.0.0.1'

# Port to listen on (non-privileged ports are > 1023)
PORT = 2938

# Just the version
version = "0.0.1"

# The printable characters from string.printable, minus \t, \r, \n
characters = ['M','B','N','W','R','g','#','Q','8','D','$','0','H','@','m','&','E','O','9','6','d','b','A','p', 'K','q','Z','G','U','X','P','5','a','2','S','k','e','h','4','V','3','I','w','F','y','o','{','}','f','C','u','n','1','z','%','s','t','x','Y','J','[','T', ']','j','7','L','i','l','v','c','?',')','(','/','r','<','>','*','=','|','+','!','_',';','^',':','~',',','.','-','`',' ']

# The brightnesses of each character, previously calculated by creating an image containing only that character
global_brightnesses = np.array([156.1,157.6,159.9,160.6,164.8,165.6,166.3,167.1,168.9,169.9,171.2,171.6,172.1,172.2,172.4,173.5,173.7,173.9,173.9,174.0,174.7,174.7,174.9,176.3,176.3,176.4,176.7,177.4,179.2,179.5,179.6,180.0,181.2,181.4,182.1,182.2,182.3,184.6,184.9,185.7,186.7,188.1,189.1,189.7,192.0,192.3,194.5,194.5,195.1,195.7,195.7,195.8,196.0,196.3,196.7,196.8,197.9,198.6,198.7,198.9,199.2,199.2,199.2,200.0,200.5,202.4,202.4,203.3,203.9,205.9,208.9,214.7,214.8,215.2,215.5,215.8,215.8,220.8,223.1,223.1,225.2,225.6,229.5,230.5,231.7,238.0,238.7,239.0,246.5,246.5,248.3,255.0])

# For the pgp encryption
#key_path = "./data/k"
#share_path = "./data/share"
#passphrase = "darker"


client = md5("-".encode()).hexdigest()

indices = [0] * 256
frames = 0
start = time.time()

