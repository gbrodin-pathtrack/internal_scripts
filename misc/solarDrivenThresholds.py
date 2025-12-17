def curr_driven(vbatt : int):
    if(vbatt > 414):
        return "1"
    elif(vbatt > 402):
        return "hysteresis"
    elif(vbatt > 396):
        return "2"
    elif(vbatt > 390):
        return "hysteresis"
    elif(vbatt > 384):
        return "3"
    elif(vbatt > 378):
        return "hysteresis"
    elif(vbatt > 372):
        return "4"
    elif(vbatt > 366):
        return "hysteresis"
    else:
        return "MAX"
    
def new_driven(vbatt : int):
    if(vbatt > 414):
        return "1"
    elif(vbatt > 402):
        return "hysteresis"
    elif(vbatt > 396):
        return "2"
    elif(vbatt > 390):
        return "hysteresis"
    elif(vbatt > 384):
        return "3"
    elif(vbatt > 378):
        return "hysteresis"
    elif(vbatt > 372):
        return "4"
    elif(vbatt > 366):
        return "hysteresis"
    else:
        return "5"

def curr_assisted(vbatt : int):
    if(vbatt > 414):
        return "1"
    elif(vbatt > 408):
        return "hysteresis"
    elif(vbatt > 402):
        return "1.5"
    elif(vbatt > 396):
        return "hysteresis"
    elif(vbatt > 390):
        return "2"
    elif(vbatt > 384):
        return "hysteresis"
    elif(vbatt > 378):
        return "2.5"
    elif(vbatt > 372):
        return "hysteresis"
    else:
        return "MAX"
    
    
def new_assisted(vbatt : int):
    if(vbatt > 406):
        return "1"
    elif(vbatt > 400):
        return "hysteresis"
    elif(vbatt > 388):
        return "2"
    elif(vbatt > 382):
        return "hysteresis"
    elif(vbatt > 378):
        return "3"
    elif(vbatt > 372):
        return "hysteresis"
    else:
        return "5"

i = 415
while i > 365:
    whole = int(i/100)
    frac = i % 100
    print("%d.%02dV = %s" % (whole, frac, new_assisted(i)))
    i -= 1