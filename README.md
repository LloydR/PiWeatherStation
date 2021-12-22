# PiWeatherStation
special driver and RFM69 code on Raspberry Pi 3 B running WeeWX listening to a Davis ISS Vantage Pro 2

Raspberry Pi 3 B running WeeWX software with “home made” Python programs to interface between the Davis ISS (integrated sensor suite) wireless signal and the Weewx software. These “home made” programs are mypiweewxdriver.py, Dissdata.py, DissRFM69.py, DissRFM69registers.py.  There is also a Dissexample.py that is test code to check receipt of the Davis ISS packets. 

Dissdata.py reads the RFM69 radio receiver and uses DissRFM69.py and DissRFM69registers.py. It outputs 2 files on /var/ramdisk wxdata and bucket which mypiweewxdriver.py uses to feed Weewx the data it needs, temperature, rain, wind, wind direction, etc. The Raspberry Pi also has a BME-280 barometer, humidity and temperature (indoor temp) instrument which is used by Dissdata.py as well as a real time clock. The RTC is used by the Raspberry Pi system.
In addition there is a line added to /etc/rc.local to start the Dissdata.py program upon bootup.  
python3 /home/weewx/bin/user/Dissdata.py

There is also a Dissexample.py that is test code to check receipt of the Davis ISS packets. 
Dissexample.py uses DissRFM69.py and DissRFM69registers.py to work - output is on terminal

Ramdisk 
edit /etc/fstab
add the line 
tmpfs /var/ramdisk tmpfs nodev,nosuid,size=1M 0 0

WeeWX is added using the setup.py since we modified it and want to add a driver and other py nonstandard programs (DissRFM69.py etc)

In /home/weewx/bin/user is where I put the 4 python files Dissdata.py DissRFM69.py DissRFM69registers.py mypiweewxdriver.py

This is all based upon DeKay and his work back in 2014 using a Moteino. 
As in 

https://github.com/dekay/im-me/blob/master/pocketwx/src/protocol.txt


https://madscientistlabs.blogspot.com/2014/01/more-than-one-way-to-skin-cat.html

 
