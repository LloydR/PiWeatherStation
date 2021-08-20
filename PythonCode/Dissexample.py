#!/usr/bin/env python2

# This is a Python RFM69 testing program written by Lloyd Brown on about 3/7/2017
# It is to check function of the RFM69 transceiver and the BME280
# All so I can run weewx without a Moteino and have a better handle
# on what is being sent to weewx so I can get rid of the zeros
# when the Pi and Arduino are rebooted.
# It started out as a Python port from low power lab cpp program
# The port was done by etrombly which he has in github
# I started changing things to suit my purpose and follow Dekay
# for reading the Davis ISS packages

# Davis ISS sends 10 bytes lsb first so the bytes have to be reverse, the last 2 bytes are always 0xFF 0xFF
# The first byte upper nibble is type 
# Davis packet types, also defined by kobuki https://github.com/dekay/DavisRFM69/wiki/Message-Protocol
# Byte 0: This is a header. The upper nibble is the sensor the data is from
#define VP2P_UV             0x4 // UV index
#define VP2P_RAINSECS       0x5 // seconds between rain bucket tips
#define VP2P_SOLAR          0x6 // solar irradiation
#define VP2P_TEMP           0x8 // outside temperature
#define VP2P_WINDGUST       0x9 // 10-minute wind gust
#define VP2P_HUMIDITY       0xA // outside humidity
#define VP2P_RAIN           0xE // rain bucket tips counter
# The rates they show up at are (with a transmitter ID of 1, i.e. one packet every 2.5 s):

# 40 shows either every 47.5 or 50 seconds
# 50 shows every 10 seconds
# 60 shows every 50 seconds
# 80 shows every 10 seconds
# 90 shows either 45, 47.5, or 50 seconds
# a0 shows alternately every 40 seconds and 10 seconds (interesting!)
# e0 shows every 10 seconds


import DissRFM69
from DissRFM69registers import *
from datetime import datetime, timezone
import time

# Now we want to use the BME-280 to get barometer and humidity and temperature
#
#
import smbus2
import bme280

port = 1
address = 0x76
bus = smbus2.SMBus(port)

bme280.load_calibration_params(bus, address)

# the sample method will take a single reading and return a
# compensated_reading object
data = bme280.sample(bus, address)

# the compensated_reading class has the following attributes
print("ID of BME-280  ")
print(data.id)
print("timestamp  ")
print(data.timestamp)
print("Temp in C  ")
print(data.temperature)
print("Temp in F  ", (data.temperature * 9/5+32))
print("Pressure in hPa  ")
print(data.pressure)
print("Pressure in inhg", (data.pressure * .02953))
print("Pressure inhg corrected to sea level add 4.75224", (data.pressure * .02953 + 4.75224))
print("Humidity %?  ")
print(data.humidity)

# there is a handy string representation too
print(data)

barTime = time.time() / 60.0





count = 0
channel = 0
reversedbits = []

DAVISFREQ = [
            14932604,14784625,14940818,15121665,14990157,14850390,15171004,15047694,14891494,15080577,14965480,14809302,15023039,
            15146335,14916156,14825728,15006583,15097010,14866832,15187438,14957266,14801066,15031245,15129908,14899722,15179225,
            14842177,14981928,15064128,15154548,14792860,14924384,15105224,14998370,14858618,15039458,15195666,15088797,14883273,
            14949046,15055915,14817515,15138114,15014819,14907950,15072356,14833942,15113452,14875052,14973708,15162776
            ]
def freqHop(channel):
    channel += 1
    if (channel > 50):
        channel = 0
    test.setFrequency(DAVISFREQ[channel])        
    return channel

    
#    
# have a packet process it and put values in the various weather related variables
#
def processPacket(pac):
# Every packet has wind speed, direction, and battery status in it
# Wind speed is in pac[1]
# Wind direction is in pac[2]
# Battery status Bit 3 in the low order nibble of Byte 0 indicates if the transmitter battery is low. 
# The bit is set to zero if the battery is OK,
# Lowest three bits in the low order nibble is the transmitter ID
# From https://github.com/dekay/DavisRFM69/wiki/Message-Protocol and other places
    SENSOR_OFFLINE = 255 # or 0xFF
    wind = pac[1]
    #windDirection_Now = ((float)radio.DATA[2] * 1.40625) + 0.3; }
    if (pac[2] == 0):
       winddir = 0
    else:
       winddir = (pac[2] * 1.40625 + .3)
    batstatus = ((pac[0] & 0x8) >> 3)
    txid = (pac[0] & 0x7)
    
    print("wind winddir batstatus txid =", wind, "{:7.2f}".format(winddir), batstatus, txid,)
    
    typepac = (pac[0] >> 4) # you prob think I could have done a if pac[0] but lower nibble is ID and BatStat
    if typepac == 4:  #It is UV index
        if (pac[3] != SENSOR_OFFLINE):
          uvindex = ((pac[3] << 8) + pac[4]) >> 4
          uvindex = (uvindex - 4)/200.0
          #tt = word(radio.DATA[3], radio.DATA[4]);
          #tt = tt >> 4;
          #loopData.uV = (uint8_t)((float)(tt-4) / 200.0);
        else:
          uvindex = 0
        print("uvindex =", uvindex)
        
    elif typepac == 5:  # it is Rain Rate
        if (pac[3] == 255):
           rainrate = 0
        else:
           rainrate = pac[4] >> 4
           if (rainrate < 4):
              rainrate = ((pac[3] >> 4) + pac[4] - 1)
           else:
              rainrate = pac[3] + ((pac[4] >> 4)-4) * 256
        # From https://github.com/Scott216/Weather_Station_Data/blob/master/Weather_Station/Weather_Station.ino
        #byte4MSN = radio.DATA[4] >> 4;
        #if ( byte4MSN < 4 )
        #{ rainSeconds =  (radio.DATA[3] >> 4) + radio.DATA[4] - 1; }  
        #else
        #{ rainSeconds = radio.DATA[3] + (byte4MSN - 4) * 256; }   
        print("rainrate =", rainrate)
        
    elif typepac == 6:  # it is Solar Radiation
        if ((pac[3]) != SENSOR_OFFLINE):
           solarRadiation = (((pac[3] << 2) + (pac[4]>> 6)) * 1.758488)
        else:
           solarRadiation = 0
        print("solarRadiation =", solarRadiation)
        
    elif typepac == 8:  # it is temperature
        outsideTemperature = ((pac[3] << 8) + pac[4]) >> 4
        #loopData.outsideTemperature = (int16_t)(word(radio.DATA[3], radio.DATA[4])) >> 4;
        print("outsideTemperature =", outsideTemperature)
        
    elif typepac == 9:  # it is Wind Gust
       windGust = pac[3]
       gustIndex = pac[5] >> 4
       #The upper nibble of byte 5 contains an index ranging from 0 to 9 that indicates which of the last ten message 9 intervals the gust occurred in
       print("windGust =", windGust)
       
    elif typepac == 10: # it is humidity
       outsideHumidity = (((pac[4] >> 4) << 8) + pac[3]) / 10.0
       print("outsideHumidity =", outsideHumidity)
       
    elif typepac == 14: # it is rain
       rainBucTipNum = pac[3] 
       print("BucketTip# =", rainBucTipNum)
       
    else:
        print("should not be here", typepac)
         
    return
       
    
    
    
    
    
    
    
    
    
# CRC Calculation Taken from http://stackoverflow.com/questions/25239423/crc-ccitt-16-bit-python-manual-calculation
# The asterisk "*" is used in Python to define a variable number of arguments. The asterisk character has to precede a variable identifier in the parameter list.

POLYNOMIAL = 0x1021
PRESET = 0

def _initial(c):
    crc = 0
    c = c << 8
    for j in range(8):
        if (crc ^ c) & 0x8000:
            crc = (crc << 1) ^ POLYNOMIAL
        else:
            crc = crc << 1
        c = c << 1
    return crc
# Thought this was causing problems but nope -  
# was getting an invalid syntax down in crcb
# also had a couple unmatched ) way down in calling the crcb
# This library is interesting for real use cases because it pre-computes a table of crc for enhanced speed.
# This is called in the main routine that populates _tab so when crcb is called it can do some kind of table XOR
_tab = [ _initial(i) for i in range(256) ]

def _update_crc(crc, c):
    cc = 0xff & c
    
    tmp = (crc >> 8) ^ cc
    crc = (crc << 8) ^ _tab[tmp & 0xff]
    crc = crc & 0xffff
    #print (crc)

    return crc

def crc(str):
    crc = PRESET
    for c in str:
        crc = _update_crc(crc, ord(c))
    return crc

# change this so it gets a length to look at will be passing reversedbits and 6   
# problems with this when it had crcb(*i)
# len is a built in function can't name a variable len  maybe
# Seems to be the  *i it had and me trying to send it a list
def crcb(i, size): 
    
    crc = PRESET
    for c in i[:size]:
        crc = _update_crc(crc, c)
    return crc

# variables for chasing the try 25 times for reception
#and recpetion statistics
receivedStreak = 0
crcErrors = 0
packetsMissed = 0
packetsReceived = 0
numResynch = 0
lastRxTime = 0.0
hopCount = 0
PACKET_INTERVAL = 2555.0 # 2.555 seconds
#
# This is the equivalent of the setup() portion of the arduino code
#
test = DissRFM69.RFM69(RF69_915MHZ, 1, 1, True)
#initializes to 915 MHz
print("RFM69 class initialized")
print("reading all registers")
#results = test.readAllRegs()
#for result in results:
#    print result
#didn't like the binary so added hex to RFM69.py on 3/6/2017 
results = test.readAllRegsHex()
#for result in results:
#    print result 

print("Performing rcCalibration")
test.rcCalibration()
print("setting high power")
test.setHighPower(True)
print("Checking temperature")
print(test.readTemperature(0))

# Now let us make a frequency change and set to a Davis ISS frequency.
test.setFrequency(DAVISFREQ[channel])


# This is the equivalent of the "loop()" portion
#
# 3/11/2017 added the ability to try and get the next packet even if no reception
# or a bad crc
# hopCount strts as 0, a good packet sets it to 1
# if no reception (receiveDone() returns and hopCount > 0) check time - 
# if time > PACKET_INTERVAL + 200 then hop do it for 25 times
#

test.receiveBegin()
while (count < 3000):


    #print "reading"
#jebus this was a "while true" get rid of it and go receive done
    #test.receiveBegin()
    #localtime = time.asctime( time.localtime(time.time()) )
    #print "Local current time :", localtime
    
    # Check every 10 milliseconds
    time.sleep(.01)
    #Get milliseconds and minutes
    nowTime = time.time()
    nowTimems = nowTime * 1000.0
    nowTimemin = nowTime / 60.0
    
    if ((nowTimemin - barTime) > 1.0):
       # a minute has passed need to read the barometer
       barTime = nowTimemin
       databar = bme280.sample(bus, address)
       print(databar)
#
# receiveDone() returns True or False
# if PAYLOADLEN is > 0 then True else False
# receiveBegin() sets PAYLOADLEN to 0
# Interrupt handler sets it to a non 0 value




# Receive done is a check to see if we had an interrupt by looking at PAYLOADLEN > 0 
# if so returns TRUE if not returns FALSE



# need to change this so it does like VP2_LRB.cpp
# which is check time & if > PACKET_INTERVAL (2555 milliseconds) + 200 then
# hop the frequency 
# If a packet was not received at the expected time, hop the radio anyway
# in an attempt to keep up.  Give up after 25 failed attempts.  Keep track
# of packet stats as we go.  I consider a consecutive string of missed
# packets to be a single resync.  Thx to Kobuki for this algorithm.
#if ((hopCount > 0) && ((millis() - lastRxTime) > (hopCount * PACKET_INTERVAL + 200))) 
#  {
#  packetStats.packetsMissed++;
#  if (hopCount == 1) packetStats.numResyncs++;
#  if (++hopCount > 25) hopCount = 0;
#  radio.hop();
#  }
# packet stats are CRCerrors, receivedStreak, numResynch, packetsMissed, packetsReceived
# guess what there is no && AND in python

# Ah yes - changed this from while not time.sleep() to if may want to do that in the while(count) statement????
# otherwise this may a busy program spinning its wheels

    if (test.receiveDone() == False):
        # NO INTERRUPT check time to see if we need to hop
        
        if ((hopCount > 0) and ((nowTimems - lastRxTime) > (hopCount * PACKET_INTERVAL + 200.0))):
            packetsMissed += 1
            if (hopCount == 1):
              numResynch += 1
            hopCount += 1
            if (hopCount > 25):
             hopCount = 0
            channel = freqHop(channel)
            print("Channel is = ", channel)
            print(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])


# fifo read in interrupt handler and now we have to reverse the bits 
# DavisRFM69.cpp has an interrupt handler that does this with a wiringpi function
# DissRFM69 also has an interrupt handler which I changed to match DavisRFM69.cpp
# as of 3/8/2017 the data sucks
# 3/8/2017 put in hop() and the subsequent data looks good
    #print "And the DATA is "
    #print [hex(x) for x in test.DATA]
    
    
    # Interrupt happened - got something lets check it
    else:
        #localtime = time.asctime( time.localtime(time.time()) )
        #print "Local current time :", localtime
        # Get milliseconds had just one datetime.utcnow did not like it
        # because datetime class is in datetime module
        print(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        lastRxTime = nowTimems
        packetsReceived += 1
        print("RSSI:%s" % (test.RSSI))
        for x in test.DATA:
           #print hex(x),
           reversedbits.append(test.revbit(x))
        
        print([hex(x) for x in reversedbits])
    #
    # OK let us check for a good packet
    #
        if ((reversedbits[8] == 0xFF and reversedbits[9] == 0xFF) and (reversedbits[0] == 0x40 or  
           reversedbits[0] == 0x50 or reversedbits[0]==0x60 or reversedbits[0]== 0x80 or 
           reversedbits[0]== 0x90 or reversedbits[0]==0xA0 or reversedbits[0]==0xE0)
           ):
           #print "Good packet"
        # CRC-CCITT 0x1021 x16 + x12 + x5 + 1
        # So if a good packet need to check CRC16_ccitt
        # What to do? Get https://github.com/gtrafimenkov/pycrc16 or https://pypi.python.org/pypi/crc16/0.1.1
        # or https://pypi.python.org/pypi/PyCRC
        # or http://stackoverflow.com/questions/25239423/crc-ccitt-16-bit-python-manual-calculation
        # was doing << 4 not good for a byte which has 8 bits
           crcresult = crcb(reversedbits, 6)
           if (crcresult == ((reversedbits[6] << 8) + reversedbits[7])):
               #print "CRC is good", hex(crcresult), hex(reversedbits[6]), hex(reversedbits[7])
               # now let us proccess the packet
               processPacket(reversedbits)
               hopCount = 1
           else:
               print("CRC is bad", hex(crcresult), hex(reversedbits[6]), hex(reversedbits[7]))
               print(hex(((reversedbits[6] << 8) + reversedbits[7])))
               crcErrors += 1
               receivedStreak = 0
        channel = freqHop(channel)
        # I think we have to do this to get the radio in receive and set PAYLOADLEN = 0
        test.receiveBegin()
        count += 1
    
    reversedbits = []
if test.ACKRequested():
  test.sendACK()
print("shutting down")
print("crcErrors, packetsMissed, packetsReceived", crcErrors, packetsMissed, packetsReceived)
test.shutdown()
