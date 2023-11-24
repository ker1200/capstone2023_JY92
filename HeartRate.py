from max30102 import MAX30102
from machine import SoftI2C, I2C, Pin
import time
from hr_algorithm import *

#Define parameters for the sensor and pi pico
my_SDA_pin = 8  # I2C SDA pin number here!
my_SCL_pin = 9  # I2C SCL pin number here!
my_i2c_freq = 400000  # I2C frequency (Hz) here!

#Variables for getting a finger pulse
l_threshold = 10000
u_threshold = 14000

lastBeat = 0
beat = HeartBeat()
beatsPerMinute = 0
beatAvg = 0
prev_beatAvg = 0
rateSpot = 0

start_finger_time = 0
end_finger_time = 0
finger_on = False


RATE_SIZE = 16 #Increase this for more averaging. 4 is good.
rates = [RATE_SIZE]

#Set up the i2c communication from the pi pico to the sensor
i2c = SoftI2C(sda=Pin(my_SDA_pin),
              scl=Pin(my_SCL_pin),
              freq=my_i2c_freq)

devices = i2c.scan()

sensor = MAX30102(i2c=i2c)


# Setup the sensor with default values
sensor.setup_sensor()

while (True):
    # The check() method has to be continuously polled, to check if
    # there are new readings into the sensor's FIFO queue. When new
    # readings are available, this function will put them into the storage.
    sensor.check()

    # Check if the storage contains available samples
    if (sensor.available()):
        # Access the storage FIFO and gather the readings (integers)
        #print("Place finger on sensor please!")
        #red_sample = sensor.pop_red_from_storage()
        ir_sample = sensor.pop_ir_from_storage()
        
        #print(ir_sample, ",", red_sample)
        #Printing the raw LED values for debugging
        #if(ir_sample>0):
            #print(ir_sample)
        
        if (ir_sample> l_threshold and ir_sample < u_threshold):
            # Print the acquired data (can be plot with Arduino Serial Plotter) - Used for debugging
            #print(ir_sample)
            
            if (finger_on == False):
                start_finger_time = time.ticks_ms()
                finger_on = True
                print("Loading...")
            
            #We sensed a beat!
                print(beat.checkForBeat(ir_sample))
            if(beat.checkForBeat(ir_sample)):
                delta = time.ticks_ms() - lastBeat
                lastBeat = time.ticks_ms()
 
                beatsPerMinute = 60 / (delta / 1000.0)
                
                prev_beatAvg = beatAvg
                #print(delta)
                print("Beats Per Minute:", beatsPerMinute)
                #print("Wait")
                
                if(beatsPerMinute <= 255 and beatsPerMinute > 20):
                    rates.append(beatsPerMinute) #Store this reading in the array
                    rateSpot = rateSpot +1
                    rateSpot %= RATE_SIZE #Wrap variable
 
                    print("Calibrating..")
                    
                    #Take average of readings
                    beatAvg = 0
                    i = 0
                    for x in rates:
                       #print(x)
                       beatAvg += x
                       i += 1
                       if (i==RATE_SIZE):
                         beatAvg = beatAvg/RATE_SIZE
                         print("Beat Average:", beatAvg)
                         #print(beatAvg) #For the serial plotter
                         rates.pop(0)
                         #time.sleep_ms(5)
                         #Die Temp has an inherent resolution of 0.0625°C, but be aware that the accuracy is ±1°C.
                         #temperature_C = sensor.read_temperature()
                         #print("Temperature: ", temperature_C, "°C")
               
#        elif (end_finger_time-start_finger_time>5):
#            rates.clear()
#            finger_on=False
#            end_finger_time =0
#            start_finger_time =0
#            print("Place finger on sensor please!")
        
                
    
            
