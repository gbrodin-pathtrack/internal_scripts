seconds = "53131"

seconds = int(float(seconds))

hours = int(seconds/3600)

seconds -= hours*3600

mins = int(seconds/60)

seconds -= mins*60

print(str(hours),str(mins),str(seconds))