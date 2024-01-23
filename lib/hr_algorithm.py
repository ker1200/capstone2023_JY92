# Micropython version of SparkFun_MAX3010x_Sensor_Library
# Taken from https://github.com/kandizzy/esp32-micropython/blob/master/PPG/ppg/heartbeat.py

import time

RATE_SIZE = 16 #Increase this for more averaging. 4 is good.

class HeartBeat(object):
    
    def __init__(self):
        print("this is the heartbeat class")
        self.IR_AC_Max = 20
        self.IR_AC_Min = -20

        self.IR_AC_Signal_Current = 0
        self.IR_AC_Signal_Previous = 0
        self.IR_AC_Signal_min = 0
        self.IR_AC_Signal_max = 0
        self.IR_Average_Estimated = 0

        self.positiveEdge = 0
        self.negativeEdge = 0
        self.ir_avg_reg = 0

        self.cbuf = [0] * 32
        self.offset = 0

        self.FIRCoeffs = [172, 321, 579, 927, 1360, 1858, 2390, 2916, 3391, 3768, 4012, 4096]

    def averageDCEstimator(self, wp, x):
        wp += ( ( ( x << 15) - wp) >> 4)
        self.ir_avg_reg = wp
        return (wp >> 15)

    def mul16(self, x, y):
        return(x * y)

    def lowPassFIRFilter(self, din):
        self.cbuf[self.offset] = din

        z = self.mul16(self.FIRCoeffs[11], self.cbuf[(self.offset - 11) & 0x1F])
      
        for i in range(11):
            z += self.mul16(self.FIRCoeffs[i], self.cbuf[(self.offset - i) & 0x1F] + self.cbuf[(self.offset - 22 + i) & 0x1F])

        self.offset += 1
        self.offset %= 32 #Wrap condition

        return(int(z >> 15))

    def checkForBeat(self, sample):
        beatDetected = False

        #  Save current state
        self.IR_AC_Signal_Previous = self.IR_AC_Signal_Current

        #  Process next data sample
        self.IR_Average_Estimated = self.averageDCEstimator(self.ir_avg_reg, sample)
        self.IR_AC_Signal_Current = sample - self.IR_Average_Estimated #self.lowPassFIRFilter(sample - self.IR_Average_Estimated)

        print("prev: " + str(self.IR_AC_Signal_Previous) + "\ncurr: " + str(self.IR_AC_Signal_Current))
        #  Detect positive zero crossing (rising edge)
        if ((self.IR_AC_Signal_Previous < 0) and (self.IR_AC_Signal_Current >= 0)):
            self.IR_AC_Max = self.IR_AC_Signal_max
            self.IR_AC_Min = self.IR_AC_Signal_min

            self.positiveEdge = 1
            self.negativeEdge = 0
            self.IR_AC_Signal_max = 0

            #if ((IR_AC_Max - IR_AC_Min) > 100 & (IR_AC_Max - IR_AC_Min) < 1000)
            if ((self.IR_AC_Max - self.IR_AC_Min) > 20 and (self.IR_AC_Max - self.IR_AC_Min) < 1000):
              beatDetected = True

        #  Detect negative zero crossing (falling edge)
        if ((self.IR_AC_Signal_Previous > 0) and (self.IR_AC_Signal_Current <= 0)):
            self.positiveEdge = 0
            self.negativeEdge = 1
            self.IR_AC_Signal_min = 0

        #  Find Maximum value in positive cycle
        if (self.positiveEdge and (self.IR_AC_Signal_Current > self.IR_AC_Signal_Previous)): 
            self.IR_AC_Signal_max = self.IR_AC_Signal_Current

        #  Find Minimum value in negative cycle
        if (self.negativeEdge and (self.IR_AC_Signal_Current < self.IR_AC_Signal_Previous)):
            self.IR_AC_Signal_min = self.IR_AC_Signal_Current
        
        return beatDetected
    
class DetectHeartbeat(object):
    def __init__(self):
        #Variables for getting a finger pulse
        self.l_threshold = 50000
        self.u_threshold = 60000

        self.lastBeat = 0
        self.beat = HeartBeat()
        self.beatsPerMinute = 0
        self.beatAvg = 0
        self.prev_beatAvg = 0
        self.rateSpot = 0
        self.delta = 0

        self.start_finger_time = 0
        self.end_finger_time = 0
        self.finger_on = False
            
        self.rates = [RATE_SIZE]

    def detectHeartbeat(self, ir):
        if (ir > self.l_threshold and ir < self.u_threshold):
            if (self.finger_on == False):
                self.start_finger_time = time.ticks_ms()
                self.finger_on = True
                print("Loading...")
            
            #We sensed a beat!
            if(self.beat.checkForBeat(ir)):
                print("Beat\n")
                self.delta = time.ticks_ms() - self.lastBeat
                self.lastBeat = time.ticks_ms()

                self.beatsPerMinute = 60 / (self.delta / 1000.0)
                
                self.prev_beatAvg = self.beatAvg
                print(self.delta)
                print("Beats Per Minute:", self.beatsPerMinute)
                
                if(self.beatsPerMinute < 255 and self.beatsPerMinute > 20):
                    self.rates.append(self.beatsPerMinute) #Store this reading in the array
                    self.rateSpot = self.rateSpot + 1
                    self.rateSpot %= RATE_SIZE #Wrap variable

                    print("Calibrating..")
                    
                    #Take average of readings
                    self.beatAvg = 0
                    i = 0
                    for x in self.rates:
                        #print(x)
                        self.beatAvg += x
                        i += 1
                        if (i==RATE_SIZE):
                            self.beatAvg = self.beatAvg / RATE_SIZE
                            print("Beat Average:", self.beatAvg)
                            #print(beatAvg) #For the serial plotter
                            self.rates.pop(0)
                        
    def getBeatAverage(self):
        return self.beatAvg