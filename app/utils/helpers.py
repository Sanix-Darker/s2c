import sys, traceback

def get_trace():
    print("Exception in code:")
    print("-"*60)
    traceback.print_exc(file=sys.stdout)
    print("-"*60)

