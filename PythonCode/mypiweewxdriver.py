#
# based on FileParse.py by Matthew Wall and also a driver by Neville Davis
# https://www.dropbox.com/s/a0fq254dwlpgm0l/piweather.py?dl=0
# 

# Driver for the Raspberry Pi3 which has the RFM69 
# which takes information from the Davis ISS
# and BME280 modules
# 
# 
# 
# *args and **kwargs  https://pythontips.com/2013/08/04/args-and-kwargs-in-python-explained/
#
#
# Create a file in the user directory, say mydriver.py. This file will contain the driver class as well as any hardware-specific code. 
# Do not put it in the weewx/drivers directory or it will be deleted when you upgrade weeWX.
# file driver.py should go to the user directory. In your case that will be: /home/weewx/bin/user.

# Inherit from the abstract base class weewx.drivers.AbstractDevice. Try to implement as many of its methods as you can. 
# At the very minimum, you must implement the first three methods, loader, hardware_name, and genLoopPackets.

# loader
# This is a factory function that returns an instance of your driver. It has two arguments: the configuration dictionary, and a reference to the weeWX engine.

# hardware_name
# Return a string with a short nickname for the hardware, such as "ACME X90"

# genLoopPackets
# This should be a generator function that yields loop packets, one after another. Don't worry about stopping it: the engine will do this when an archive record is due. 
# A "loop packet" is a dictionary. At the very minimum it must contain keys for the observation time and for the units used within the packet.
#
# The fileparse driver is perhaps the most simple example of a weeWX driver. It reads name-value pairs from a file and uses the values as sensor 'readings'. 
# The code is located in extensions/fileparse/bin/user/fileparse.py
#
# A couple of observation types are tricky. In particular, rain. 
# Generally, weeWX expects to see a packet with the amount of rain that fell in that packet period included as observation rain. 
# It then sums up all the values to get the total rainfall and emits that in the archive record. 
# Davis ISS sends bucket tipa, 1 tip = 0.01", only goes to 127 0x7f before it goes to 0 

# This driver will read data from a file /var/ramdisk/wxdata.  Each line of the file is a 
# name=value pair, for example:
#
# temperature=50
# humidity=54
# in_temperature=75
#
# Rev 0.1
# It will also read another file var/ramdisk/bucket 
# which just has the bucket tip number from the Davis ISS
# That way Dissdata does not have to worry about
# lost packets etc.


import syslog
import time
import weewx.drivers
import os, os.path

DRIVER_NAME = 'mypiweewxdriver'
DRIVER_VERSION = "0.0"

def logmsg(dst, msg):
    syslog.syslog(dst, 'mypiweewxdriver: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)


def _get_as_float(d, s):
    v = None
    if s in d:
        try:
            v = float(d[s])
        except ValueError as e:
            logerr("cannot read value for '%s': %s" % (s, e))
    return v

    

def loader(config_dict, engine):
    return MyPiweewxDriver(**config_dict[DRIVER_NAME])
    
    
prevbucknum = None    
# To define the hardware_name it appears it has to go within a class 
# Python classes provide all the standard features of Object Oriented Programming: 
# the class inheritance mechanism allows multiple base classes, 
# a derived class can override any methods of its base class or classes, 
# and a method can call the method of a base class with the same name. 
# Objects can contain arbitrary amounts and kinds of data. 
# As is true for modules, classes partake of the dynamic nature of Python: they are created at runtime, and can be modified further after creation.

#
# This class has an initialization and then a genLoopPackets
#
class MyPiweewxDriver(weewx.drivers.AbstractDevice):
    """weewx driver that reads data from Davis ISS"""

    def __init__(self, **stn_dict):
        # where to find the data file
        self.path = stn_dict.get('path', '/var/ramdisk/wxdata')
        # how often to poll the weather data file, seconds
        # This driver is asynchronous with the data gatherer
        # does not matter if we poll a packet twice or don't poll a packet
        # because each data value (other than windSpeed and windDir is set only every X polls anyway.
        self.poll_interval = float(stn_dict.get('poll_interval', 2.53))
        

        loginf("data file is %s" % self.path)
        loginf("polling interval is %s" % self.poll_interval)
  

    def genLoopPackets(self):
        global prevbucknum
        while True:
            #read whatever values we can get from the file
            start_time = time.time()
            mod_time = os.path.getmtime('/var/ramdisk/wxdata')
            if ((start_time - mod_time) < 10.0):  # if we missed 4 packets, let us wait a while
               # Create Loop packet
               try: # If it does not open then DissData has not gotten a good packet from Davis ISS
                  f = open('/var/ramdisk/wxdata', 'r')
                  input = f.read()
                  f.close()
                  rd = open('/var/ramdisk/bucket', 'r')
                  rdinput = rd.read()
                  rd.close()
                  # {} are special in that you can give custom id's to values like a = {"John": 14}. 
                  # Now, instead of making a list with ages and remembering whose age is where, you can just access John's age by a["John"]
                  data = {} # [] is a list {} is a dictionary or set
                  try:
                      for line in input.splitlines(): # Returns a list of the lines in the string, breaking at line boundaries.
                          eq_index = line.find('=') # Returns the index of the first occurrence of the string searched for.
                          # word[:2]   character from the beginning to position 2 (excluded)
                          # word[4:]   characters from position 4 (included) to the end
                          name = line[:eq_index].strip() # strip() returns a copy of the string with the leading and trailing characters removed.
                          value = line[eq_index + 1:].strip()
                          data[name] = value
                  except Exception as e:
                      logerr("read failed: %s" % e)

               # map the data into a weewx loop packet
                  _packet = {'dateTime': int(time.time() + 0.5),
                          'usUnits': weewx.US}
                  for vname in data:
                      # Don't have a label_map, don't need it.  All names are the same as the dictionary
                      _packet[vname] = _get_as_float(data, vname)
                  
                  
                  # Take care of the bucket tips    
                  bucknum = int(rdinput)
                  if prevbucknum is None: # first time through
                     rain = 0.0
                  elif (bucknum == prevbucknum): #no rain no change
                     rain = 0.0
                  else: #something changed
                     if (prevbucknum > bucknum): #went through 127 
                        rain = ((128 - prevbucknum) + bucknum) * .01
                     else:
                        rain = (bucknum - prevbucknum) * .01
                  prevbucknum = bucknum  # after all done set equal
                  _packet['rain'] = rain
                         
                      

                  yield _packet
                  
                  sleep_time = (start_time - time.time()) + self.poll_interval
                  if sleep_time > 0:
                      time.sleep(sleep_time)
               except IOError as e:
                      time.sleep(60) # sleep for a minute to let Dissdata get a packet
            else:
               time.sleep(25) # the file has not been updated in 4 cycles, let us wait for 10 cycles
               
               
    @property
    def hardware_name(self):
        return "MyPiweewx"


        
        
if __name__ == "__main__":
    import weeutil.weeutil
    station = MyPiweewxDriver()
    for packet in station.genLoopPackets():
        print(weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet)