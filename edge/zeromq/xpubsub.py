import zmq

context = zmq.Context()

xsub_socket = context.socket(zmq.XSUB)
xsub_socket.bind("tcp://*:6000")  

xpub_socket = context.socket(zmq.XPUB)
xpub_socket.bind("tcp://*:6001")  

print("Starting XPUB–XSUB proxy...")
zmq.proxy(xsub_socket, xpub_socket)
