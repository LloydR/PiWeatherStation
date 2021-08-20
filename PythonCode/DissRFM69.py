#!/usr/bin/env python2

from DissRFM69registers import *
import spidev
import RPi.GPIO as GPIO
import time

class RFM69(object):
    def __init__(self, freqBand, nodeID, networkID, isRFM69HW = False, intPin = 18, rstPin = 29, spiBus = 0, spiDevice = 0):

        self.freqBand = freqBand
        self.address = nodeID
        self.networkID = networkID
        self.isRFM69HW = isRFM69HW
        self.intPin = intPin
        self.rstPin = rstPin
        self.spiBus = spiBus
        self.spiDevice = spiDevice
        self.intLock = False
        self.mode = ""
        self.promiscuousMode = False
        self.DATASENT = False
        self.DATALEN = DAVIS_PACKET_LEN
        self.SENDERID = 0
        self.TARGETID = 0
        self.PAYLOADLEN = 0
        self.ACK_REQUESTED = 0
        self.ACK_RECEIVED = 0
        self.RSSI = 0
        self.DATA = []
        
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.intPin, GPIO.IN)
        GPIO.setup(self.rstPin, GPIO.OUT)

        frfMSB = {RF69_315MHZ: RF_FRFMSB_315, RF69_433MHZ: RF_FRFMSB_433,
                  RF69_868MHZ: RF_FRFMSB_868, RF69_915MHZ: RF_FRFMSB_915}
				  
        frfMID = {RF69_315MHZ: RF_FRFMID_315, RF69_433MHZ: RF_FRFMID_433,
                  RF69_868MHZ: RF_FRFMID_868, RF69_915MHZ: RF_FRFMID_915}
				  
        frfLSB = {RF69_315MHZ: RF_FRFLSB_315, RF69_433MHZ: RF_FRFLSB_433,
                  RF69_868MHZ: RF_FRFLSB_868, RF69_915MHZ: RF_FRFLSB_915}

        self.CONFIG = {
          0x01: [REG_OPMODE, RF_OPMODE_SEQUENCER_ON | RF_OPMODE_LISTEN_OFF | RF_OPMODE_STANDBY],
          #no shaping
          0x02: [REG_DATAMODUL, RF_DATAMODUL_DATAMODE_PACKET | RF_DATAMODUL_MODULATIONTYPE_FSK | RF_DATAMODUL_MODULATIONSHAPING_00],
          #default:4.8 KBPS but we will go with 19200 which is what Davis does
          0x03: [REG_BITRATEMSB, RF_BITRATEMSB_19200],
          0x04: [REG_BITRATELSB, RF_BITRATELSB_19200],
          #default:5khz, (FDEV + BitRate/2 <= 500Khz) but we will go with 4800 Hz which is what Davis does
          0x05: [REG_FDEVMSB, RF_FDEVMSB_4800],
          0x06: [REG_FDEVLSB, RF_FDEVLSB_4800],

		  #Question why frfMSB vs RF_FRFMID_915  This sets the frequency - must be the freqBand such as comes from 
		  # test = RFM69.RFM69(RF69_915MHZ, 1, 1, True)
          0x07: [REG_FRFMSB, frfMSB[freqBand]],
          0x08: [REG_FRFMID, frfMID[freqBand]],
          0x09: [REG_FRFLSB, frfLSB[freqBand]],
		  # // TODO: Should use LOWBETA_ON, but having trouble getting it working
          0x0B: [REG_AFCCTRL, RF_AFCCTRL_LOWBETA_OFF],
          # looks like PA1 and PA2 are not implemented on RFM69W, hence the max output power is 13dBm
          # +17dBm and +20dBm are possible on RFM69HW
          # +13dBm formula: Pout=-18+OutputPower (with PA0 or PA1**)
          # +17dBm formula: Pout=-14+OutputPower (with PA1 and PA2)**
          # +20dBm formula: Pout=-11+OutputPower (with PA1 and PA2)** and high power PA settings (section 3.3.7 in datasheet)
          #0x11: [REG_PALEVEL, RF_PALEVEL_PA0_ON | RF_PALEVEL_PA1_OFF | RF_PALEVEL_PA2_OFF | RF_PALEVEL_OUTPUTPOWER_11111],
          #over current protection (default is 95mA)
          #0x13: [REG_OCP, RF_OCP_ON | RF_OCP_TRIM_95],
		# The Dekay DavisRFM69.cpp initializes 0x0B and 0x18 actually B is no change and 18 is confused also
		# // Not sure which is correct!
          0x18: [REG_LNA, RF_LNA_ZIN_50 | RF_LNA_GAINSELECT_AUTO], 
          # RXBW defaults are { REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_24 | RF_RXBW_EXP_5} (RxBw: 10.4khz)
          #//(BitRate < 2 * RxBw)
		#DavisRFM69.cpp set it up this way on 0x19 & 0x1A
          0x19: [REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_20 | RF_RXBW_EXP_4],
          #for BR-19200: //* 0x19 */ { REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_24 | RF_RXBW_EXP_3 },
		# DavisRFM69.cpp uses 0x1A to double the bandwidth
		  0x1A: [REG_AFCBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_20 | RF_RXBW_EXP_3],
		#
		#DavisRFM69.cpp uses 0x1E, may need to put something in here 3/7/2017 put it in
		#
          0x1E: [REG_AFCFEI, RF_AFCFEI_AFCAUTOCLEAR_ON | RF_AFCFEI_AFCAUTO_ON],
          #DIO0 is the only IRQ we're using
          0x25: [REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01],
		#DavisRFM69.cpp resets the FIFO
        # Reset the FIFOs. Fixes a problem I had with bad first packet.
		  0x28: [REG_IRQFLAGS2, RF_IRQFLAGS2_FIFOOVERRUN],
          #must be set to dBm = (-Sensitivity / 2) - default is 0xE4=228 so -114dBm Dekay has 170 may have to change this
          # with AFC may have to raise this even further see https://lowpowerlab.com/forum/rf-range-antennas-rfm69-library/long-range-parameters-for-rfm69hw-(868-915-mhz)/15/
          0x29: [REG_RSSITHRESH, 160],
		#DavisRFM69.cpp says Davis preable is 4 bytes AAAAAAAA, default is 3
          0x2d: [REG_PREAMBLELSB, RF_PREAMBLESIZE_LSB_DAVIS],
		#DavisRFM69.cpp has allow 2 errors, I set back to 0 3/7/2017
          0x2e: [REG_SYNCCONFIG, RF_SYNC_ON | RF_SYNC_FIFOFILL_AUTO | RF_SYNC_SIZE_2 | RF_SYNC_TOL_0],
          #Davis ISS first sync byte. http://madscientistlabs.blogspot.ca/2012/03/first-you-get-sugar.html
          0x2f: [REG_SYNCVALUE1, 0xCB],
		  #Davis ISS second sync byte.
          0x30: [REG_SYNCVALUE2, 0x89],
		#DavisRFM69 Fixed packet length and we'll check our own CRC
          0x37: [REG_PACKETCONFIG1, RF_PACKET1_FORMAT_FIXED | RF_PACKET1_DCFREE_OFF |
                RF_PACKET1_CRC_OFF | RF_PACKET1_CRCAUTOCLEAR_OFF | RF_PACKET1_ADRSFILTERING_OFF],
          #Davis sends 10 bytes of payload, including CRC that we check manually (Note: includes 2 byte re-transmit CRC).
          0x38: [REG_PAYLOADLENGTH, DAVIS_PACKET_LEN],
          #* 0x39 */ { REG_NODEADRS, nodeID }, //turned off because we're not using address filtering
          #TX on FIFO not empty
		#Not going to use TX so don't care LRB 3/6/2017 TX on FIFO having more than nine bytes - we'll implement the re-transmit CRC
          0x3C: [REG_FIFOTHRESH, RF_FIFOTHRESH_TXSTART_FIFOTHRESH | 0x9],
          #RXRESTARTDELAY must match transmitter PA ramp-down time (bitrate dependent)
          0x3D: [REG_PACKETCONFIG2, RF_PACKET2_RXRESTARTDELAY_2BITS | RF_PACKET2_AUTORXRESTART_ON | RF_PACKET2_AES_OFF],
          #for BR-19200: //* 0x3d */ { REG_PACKETCONFIG2, RF_PACKET2_RXRESTARTDELAY_NONE | RF_PACKET2_AUTORXRESTART_ON | RF_PACKET2_AES_OFF }, //RXRESTARTDELAY must match transmitter PA ramp-down time (bitrate dependent)
          #* 0x6F */ { REG_TESTDAGC, RF_DAGC_CONTINUOUS }, // run DAGC continuously in RX mode
          # run DAGC continuously in RX mode, recommended default for AfcLowBetaOn=0
          0x6F: [REG_TESTDAGC, RF_DAGC_IMPROVED_LOWBETA0],
		  0x71: [REG_TESTAFC, 0],
          0x00: [255, 0]
        }

        #initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(self.spiBus, self.spiDevice)
        self.spi.max_speed_hz = 4000000

        # Hard reset the RFM module
        GPIO.output(self.rstPin, GPIO.HIGH);
        time.sleep(0.1)
        GPIO.output(self.rstPin, GPIO.LOW);
        time.sleep(0.1)

        #verify chip is syncing?
        while self.readReg(REG_SYNCVALUE1) != 0xAA:
            self.writeReg(REG_SYNCVALUE1, 0xAA)

        while self.readReg(REG_SYNCVALUE1) != 0x55:
            self.writeReg(REG_SYNCVALUE1, 0x55)

        #write config
        for value in self.CONFIG.values():
            self.writeReg(value[0], value[1])

        self.encrypt(0)
        self.setHighPower(self.isRFM69HW)
        # Wait for ModeReady
        while (self.readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            pass

        GPIO.remove_event_detect(self.intPin)
        GPIO.add_event_detect(self.intPin, GPIO.RISING, callback=self.interruptHandler)

    def setFrequency(self, FRF):
        self.writeReg(REG_FRFMSB, FRF >> 16)
        self.writeReg(REG_FRFMID, FRF >> 8)
        self.writeReg(REG_FRFLSB, FRF)

    def setMode(self, newMode):
        if newMode == self.mode:
            return

        if newMode == RF69_MODE_TX:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_TRANSMITTER)
            if self.isRFM69HW:
                self.setHighPowerRegs(True)
        elif newMode == RF69_MODE_RX:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_RECEIVER)
            if self.isRFM69HW:
                self.setHighPowerRegs(False)
        elif newMode == RF69_MODE_SYNTH:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SYNTHESIZER)
        elif newMode == RF69_MODE_STANDBY:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_STANDBY)
        elif newMode == RF69_MODE_SLEEP:
            self.writeReg(REG_OPMODE, (self.readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SLEEP)
        else:
            return

        # we are using packet mode, so this check is not really needed
        # but waiting for mode ready is necessary when going from sleep because the FIFO may not be immediately available from previous mode
        while self.mode == RF69_MODE_SLEEP and self.readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY == 0x00:
            pass

        self.mode = newMode;

    def sleep(self):
        self.setMode(RF69_MODE_SLEEP)

    def setAddress(self, addr):
        self.address = addr
        self.writeReg(REG_NODEADRS, self.address)

    def setNetwork(self, networkID):
        self.networkID = networkID
        self.writeReg(REG_SYNCVALUE2, networkID)

    def setPowerLevel(self, powerLevel):
        if powerLevel > 31:
            powerLevel = 31
        self.powerLevel = powerLevel
        self.writeReg(REG_PALEVEL, (self.readReg(REG_PALEVEL) & 0xE0) | self.powerLevel)

    def canSend(self):
        if self.mode == RF69_MODE_STANDBY:
            self.receiveBegin()
            return True
        #if signal stronger than -100dBm is detected assume channel activity
        elif self.mode == RF69_MODE_RX and self.PAYLOADLEN == 0 and self.readRSSI() < CSMA_LIMIT:
            self.setMode(RF69_MODE_STANDBY)
            return True
        return False

    def send(self, toAddress, buff = "", requestACK = False):
        self.writeReg(REG_PACKETCONFIG2, (self.readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        now = time.time()
        while (not self.canSend()) and time.time() - now < RF69_CSMA_LIMIT_S:
            self.receiveDone()
        self.sendFrame(toAddress, buff, requestACK, False)

#    to increase the chance of getting a packet across, call this function instead of send
#    and it handles all the ACK requesting/retrying for you :)
#    The only twist is that you have to manually listen to ACK requests on the other side and send back the ACKs
#    The reason for the semi-automaton is that the lib is ingterrupt driven and
#    requires user action to read the received data and decide what to do with it
#    replies usually take only 5-8ms at 50kbps@915Mhz

    def sendWithRetry(self, toAddress, buff = "", retries = 3, retryWaitTime = 10):
        for i in range(0, retries):
            self.send(toAddress, buff, True)
            sentTime = time.time()
            while (time.time() - sentTime) * 1000 < retryWaitTime:
                if self.ACKReceived(toAddress):
                    return True
        return False

    def ACKReceived(self, fromNodeID):
        if self.receiveDone():
            return (self.SENDERID == fromNodeID or fromNodeID == RF69_BROADCAST_ADDR) and self.ACK_RECEIVED
        return False

    def ACKRequested(self):
        return self.ACK_REQUESTED and self.TARGETID != RF69_BROADCAST_ADDR

    def sendACK(self, toAddress = 0, buff = ""):
        toAddress = toAddress if toAddress > 0 else self.SENDERID
        while not self.canSend():
            self.receiveDone()
        self.sendFrame(toAddress, buff, False, True)

    def sendFrame(self, toAddress, buff, requestACK, sendACK):
        #turn off receiver to prevent reception while filling fifo
        self.setMode(RF69_MODE_STANDBY)
        #wait for modeReady
        while (self.readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
            pass
        # DIO0 is "Packet Sent"
        self.writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_00)

        if (len(buff) > RF69_MAX_DATA_LEN):
            buff = buff[0:RF69_MAX_DATA_LEN]

        ack = 0
        if sendACK:
            ack = 0x80
        elif requestACK:
            ack = 0x40
        if isinstance(buff, basestring):
            self.spi.xfer2([REG_FIFO | 0x80, len(buff) + 3, toAddress, self.address, ack] + [int(ord(i)) for i in list(buff)])
        else:
            self.spi.xfer2([REG_FIFO | 0x80, len(buff) + 3, toAddress, self.address, ack] + buff)

        startTime = time.time()
        self.DATASENT = False
        self.setMode(RF69_MODE_TX)
        while not self.DATASENT:
            if time.time() - startTime > 1.0:
                break
        self.setMode(RF69_MODE_RX)
        
# a function that reverses bits from msb to lsb since data is transmitted from the ISS with the least significant bit first
# did not have self in it messed up TypeError: revbit() takes exactly 1 argument (2 given)
    def revbit(self, y): 
            LUT = [0x0, 0x8, 0x4, 0xc, 0x2, 0xa, 0x6, 0xe, 0x1, 0x9, 0x5, 0xd, 0x3, 0xb, 0x7, 0xf]
            MSB = LUT[y & 0xf]
            LSB = LUT[(y & 0xf0) >> 4]
            return ((MSB << 4) + LSB) #guess what you need the parens or it will shift by 4+LSB
        
		# The original interrupt handler goes along with low power lab information that has length, NodeId, then message
		# not what Dekay has setup in the initialization which is fixed length of 10 bytes and should only have the message
		# see https://github.com/LowPowerLab/RFM69/blob/master/RFM69.cpp and
		# https://github.com/dekay/DavisRFM69/blob/master/DavisRFM69.cpp
		# we are going to change this as well as set self.PAYLOADLEN and remove some if self.PAYLOADLEN > 66
		# Also receiveBegin() has a self.PAYLOADLEN
        # For some reason with this change I never get a package
        # Looks like because I set self.PAYLOADLEN  to something other than 0
        # Try setting only self.DATALEN to the Davis packet length?
    def interruptHandler(self, pin):
        self.intLock = True
        self.DATASENT = True
        self.RSSI = self.readRSSI()
		# if you are in (receive mode and (we read register 0x28 bit wise AND it with the value 0x4)) then we have a payload to read
        if self.mode == RF69_MODE_RX and self.readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY:
			# go to standby mode so no more interrupts can affect us
            
            self.setMode(RF69_MODE_STANDBY)
			
            self.DATA = self.spi.xfer2([REG_FIFO & 0x7f] + [0 for i in range(0, self.DATALEN)])[1:]
            
            
            self.PAYLOADLEN = self.DATALEN  #everything should be 10 bytes
        self.intLock = False

    def receiveBegin(self):

        while self.intLock:
            time.sleep(.1)
        # Did not work at all - gets 3 bad packets and waits 2 1/2 minutes and get 3 more bad packets
        #self.setMode(RF69_MODE_SLEEP)  # As per https://lowpowerlab.com/forum/rf-range-antennas-rfm69-library/long-range-parameters-for-rfm69hw-(868-915-mhz)/msg14565/#msg14565
        self.DATALEN = DAVIS_PACKET_LEN
        self.SENDERID = 0
        self.TARGETID = 0
        self.PAYLOADLEN = 0
        self.ACK_REQUESTED = 0
        self.ACK_RECEIVED = 0
        self.RSSI = 0
        if (self.readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY):
            # avoid RX deadlocks
            self.writeReg(REG_PACKETCONFIG2, (self.readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        #set DIO0 to "PAYLOADREADY" in receive mode
        self.writeReg(REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01)
        self.setMode(RF69_MODE_RX)

    def receiveDone(self):
        if (self.mode == RF69_MODE_RX or self.mode == RF69_MODE_STANDBY) and self.PAYLOADLEN > 0:
            self.setMode(RF69_MODE_STANDBY)
            return True
        if self.readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_TIMEOUT:
            # https://github.com/russss/rfm69-python/blob/master/rfm69/rfm69.py#L112
            # Russss figured out that if you leave alone long enough it times out
            # tell it to stop being silly and listen for more packets
            self.writeReg(REG_PACKETCONFIG2, (self.readReg(REG_PACKETCONFIG2) & 0xFB) | RF_PACKET2_RXRESTART)
        elif self.mode == RF69_MODE_RX:
            # already in RX no payload yet
            return False
        self.receiveBegin()
        return False

    def readRSSI(self, forceTrigger = False):
        rssi = 0
        if forceTrigger:
            self.writeReg(REG_RSSICONFIG, RF_RSSI_START)
            while self.readReg(REG_RSSICONFIG) & RF_RSSI_DONE == 0x00:
                pass
        rssi = self.readReg(REG_RSSIVALUE) * -1
        rssi = rssi >> 1
        return rssi

    def encrypt(self, key):
        self.setMode(RF69_MODE_STANDBY)
        if key != 0 and len(key) == 16:
            self.spi.xfer([REG_AESKEY1 | 0x80] + [int(ord(i)) for i in list(key)])
            self.writeReg(REG_PACKETCONFIG2,(self.readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_ON)
        else:
            self.writeReg(REG_PACKETCONFIG2,(self.readReg(REG_PACKETCONFIG2) & 0xFE) | RF_PACKET2_AES_OFF)

    def readReg(self, addr):
        return self.spi.xfer([addr & 0x7F, 0])[1]

    def writeReg(self, addr, value):
        self.spi.xfer([addr | 0x80, value])

    def promiscuous(self, onOff):
        self.promiscuousMode = onOff

    def setHighPower(self, onOff):
        if onOff:
            self.writeReg(REG_OCP, RF_OCP_OFF)
            #enable P1 & P2 amplifier stages
            self.writeReg(REG_PALEVEL, (self.readReg(REG_PALEVEL) & 0x1F) | RF_PALEVEL_PA1_ON | RF_PALEVEL_PA2_ON)
        else:
            self.writeReg(REG_OCP, RF_OCP_ON)
            #enable P0 only
            self.writeReg(REG_PALEVEL, RF_PALEVEL_PA0_ON | RF_PALEVEL_PA1_OFF | RF_PALEVEL_PA2_OFF | powerLevel)

    def setHighPowerRegs(self, onOff):
        if onOff:
            self.writeReg(REG_TESTPA1, 0x5D)
            self.writeReg(REG_TESTPA2, 0x7C)
        else:
            self.writeReg(REG_TESTPA1, 0x55)
            self.writeReg(REG_TESTPA2, 0x70)

    def readAllRegs(self):
        results = []
        for address in range(1, 0x50):
            results.append([str(hex(address)), str(bin(self.readReg(address)))])
        return results

		
    def readAllRegsHex(self):
        results = []
        for address in range(1, 0x50):
            results.append([str(hex(address)), str(hex(self.readReg(address)))])
        return results
		
		
		
    def readTemperature(self, calFactor):
        self.setMode(RF69_MODE_STANDBY)
        self.writeReg(REG_TEMP1, RF_TEMP1_MEAS_START)
        while self.readReg(REG_TEMP1) & RF_TEMP1_MEAS_RUNNING:
            pass
        # COURSE_TEMP_COEF puts reading in the ballpark, user can add additional correction
        #'complement'corrects the slope, rising temp = rising val
        return (int(~self.readReg(REG_TEMP2)) * -1) + COURSE_TEMP_COEF + calFactor


    def rcCalibration(self):
        self.writeReg(REG_OSC1, RF_OSC1_RCCAL_START)
        while self.readReg(REG_OSC1) & RF_OSC1_RCCAL_DONE == 0x00:
            pass

    def shutdown(self):
        self.setHighPower(False)
        self.sleep()
        GPIO.cleanup()
