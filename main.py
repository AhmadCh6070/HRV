###########################################
# Importing Necessary Libraries and Files #
###########################################

from machine import ADC,Pin, I2C
from ssd1306 import SSD1306_I2C
from fifo import Fifo
import time,utime
from piotimer import Piotimer as Timer
from led import Led
import math
import framebuf
import Heart_Empty,line # Our Own Shapes Using Bitmap
import network
from umqtt.simple import MQTTClient 
import urequests as requests 
import ujson
import json  # Add this line to import the json module

import micropython
micropython.alloc_emergency_exception_buf(200)


#############################
#  Class For Rotary Encoder #
#############################


class RotaryEncoder:
    def __init__(self, pin_a, pin_b, pin_sw, min_interval):
        self.pin_a = Pin(pin_a, Pin.IN, Pin.PULL_UP)
        self.pin_b = Pin(pin_b, Pin.IN, Pin.PULL_UP)
        self.pin_sw = Pin(pin_sw, Pin.IN, Pin.PULL_UP)
        self.Rotation = Fifo(40) #FIFO queue to store rotation events
        self.min_interval = min_interval #Min. Time Between Switch Presses To Avoid Bouncing
        self.prev_press_time = 0
        self.Menu_state = False
        self.pin_a.irq(trigger=Pin.IRQ_FALLING, handler=self.rotary_handler)
        self.pin_sw.irq(trigger=Pin.IRQ_FALLING, handler=self.toggle_handler)


    #Interrupt For Rotation
    def rotary_handler(self, pin):
        if self.pin_b.value() and self.Menu_state:
            self.Rotation.put(1)
        elif not self.pin_b.value() and self.Menu_state:
            self.Rotation.put(0)

    #Interrupt For Button
    def toggle_handler(self, pin):
        current_time = time.ticks_ms()
        if (time.ticks_diff(current_time, self.prev_press_time) > self.min_interval) and self.Menu_state:
            self.Rotation.put(2)
            self.prev_press_time = current_time
            
            
            
#############################
#  Class For Menu Display   #
#############################            


class MenuDisplay:
    #Initializes With An OLED Display Object and Options
    def __init__(self, oled, led_onboard): 
        self.oled = oled
        self.led_onboard = led_onboard
        self.options = ["HRV","Kubios HRV","History","Exit"]
        self.options_state = ""
        self.current_row = 0

    #Navigates The Arrow 
    def update(self):   
        self.oled.fill(0)
        self.oled.text("Pick A Option:",0,0,1)
        for i, state in enumerate(self.options):
            row_text = f"{i + 1}){state} "
            if i == self.current_row:
                row_text += "<--"
            self.oled.text(row_text, 0, 20 + i * 10)
        self.oled.show()
    
    #Navigates Through Options
    def next_opt(self): 
        self.current_row = (self.current_row + 1) % len(self.options)

    def prev_opt(self): 
        self.current_row = (self.current_row - 1) % len(self.options)

    #Selects the Option Chosen By The User
    def toggle_opt(self): 
        options_index = self.current_row
        if options_index == 0:
            self.options_state = "HRV"
            
        elif options_index == 1:
            self.options_state = "Kubios HRV"
            
        elif options_index == 2:
            self.options_state = "History"
            
        elif options_index == 3:
            self.options_state = "Exit"

    ####################################
    #  Function To Show Welcome Text   #
    ####################################
    
    def Welcome_Text(self):
        self.oled.fill(1)
        self.led_onboard.on()
        self.oled.text("Welcome to", 26, 5, 0)
        self.oled.text("Group 13's", 29, 15, 0)
        self.oled.text("project!", 33, 25, 0)
        self.oled.blit(heart, 47, 40) #Custom Heart Shape
        self.oled.show()
        time.sleep(3)
    
    ###########################################
    #  Function to Show Press To Start Text   #
    ###########################################

    def Press_Start(self):
        self.led_onboard.on()
        self.oled.fill(0)
        self.oled.text("Place Finger On",0,18,1)
        self.oled.text("The Sensor For",0,28,1)
        self.oled.text("5secs Then...",0,38,1)
        oled.show()
        time.sleep(2.4)
        oled.fill(0)
        self.oled.blit(line, 0,35)#Custom Line
        self.oled.text("Press the Button",0,0,1)
        self.oled.text("To start Seeing",0,12,1)
        self.oled.text("Your HeartBeat!!",0,22,1)
        self.oled.show()


    ####################################
    #  Function To Show Goodbye Text   #
    ####################################

    def GoodBye(self):
        self.oled.fill(0)
        self.oled.text("Goodbye!!!",25,26,1)
        self.oled.blit(heart, 47, 40)#Custom Heart Shape
        self.oled.show()
        time.sleep(3)
        self.led_onboard.off()
        self.oled.fill(0)
        self.oled.show()
    
    ######################################################
    #  Function To Display Info for HRV and Kubios HRV  #
    ######################################################

    def Show_Info(self,mode,MeanPPI,MeanHR,SDNN,RMSSD,SNS_OR_SD1,PNS_OR_SD2):
        
        self.oled.fill(0)
        self.oled.text('MeanPPI:'+ MeanPPI +'ms', 0, 0, 1)
        self.oled.text('MeanHR:'+ MeanHR +'bpm', 0, 9, 1)
        self.oled.text('SDNN:'+ SDNN +'ms', 0, 18, 1)
        self.oled.text('RMSSD:'+ RMSSD +'ms', 0, 27, 1)
        
        #Depending On Mode
        
        if mode == "HRV":
            self.oled.text('SD1:'+ SNS_OR_SD1 +' SD2:'+ PNS_OR_SD2 , 0, 36, 1)
        else:
            self.oled.text("SNS:"+ SNS_OR_SD1 +" PNS:"+ PNS_OR_SD2, 0, 36, 1)
        
        self.oled.text('Press Button To', 0, 46, 1)
        self.oled.text('Contine -->', 0, 55, 1)
        
        self.oled.show()
    
        time.sleep(1)
        
    ##########################################
    #  Function To Display Save For History  #
    ##########################################
    
    def Save_Info_Text(self):
        self.oled.fill(0)
        self.oled.text("Do You Want To",0,0,1)
        self.oled.text("Save This Info?",0,12,1)
        self.oled.text("SW_2 = Yes",0,28,1)
        self.oled.text("SW_0 = No",0,38,1)
        self.oled.show()


#######################################################
# The Order of Fucntions Being Calld Is From Bottom Up#
#######################################################


def calculate_threshold(arr):
    mean = sum(arr) / len(arr)
    std_dev = math.sqrt(sum((x - mean) ** 2 for x in arr) / len(arr))
    threshold = mean +  std_dev
    return threshold   

def detect_peaks(arr):
    global PPI
    peaks = []
    threshold=calculate_threshold(arr)
    for i in range(1, len(arr) - 1):
        if arr[i] > arr[i - 1] and arr[i] > arr[i + 1] and arr[i] > threshold :
            peaks.append(i)
            PPI.append(i)
    return peaks


def calculate_heart_rate(sensor_values):
    peaks = detect_peaks(sensor_values)
    if len(peaks) < 2:
        return None, None  # Return None for BPM and PPG if not enough peaks
    time_between_peaks = (peaks[-1] - peaks[0]) / len(sensor_values)
    heart_rate = 60 / time_between_peaks
    return heart_rate  # Return BPM


def stop_collection(tim):
    global collection_done, sensor_values
    collection_done = True
    heart_rate = calculate_heart_rate(sensor_values)
    display_bpm_ppg(heart_rate, sensor_values)

def collect_values():
    global collection_done, sensor_values
    collection_done = False
    Timer.init(period=3600, mode=machine.Timer.ONE_SHOT, callback=stop_collection)
    while not collection_done:
        if encoder.pin_sw.value() == 0:
            return False
        sensor_value = adc.read_u16()
        sensor_values.append(sensor_value)
        utime.sleep_ms(2)
    sensor_values.clear()
    return True
    

######################################
# Function To Show PPG Graph and BPM #
######################################

def display_bpm_ppg(bpm, sensor_values):
    DISPLAY_WIDTH = 128
    DISPLAY_HEIGHT = 64
    oled.fill_rect(0, 3, 64, 12, 1)
    # Display BPM text at the top left corner
    oled.text("BPM:", 0,4, 0)
    if bpm is not None and 30 <= bpm <= 150:
        oled.text(str(round(bpm)), 40, 4, 0)  # BPM value next to the label
    oled.fill_rect(0, 12, 128, 64, 0)

    # Allocate more space for the PPG graph
    top_margin = 12  # Reduce the top margin to give more space to the graph
    graph_height = DISPLAY_HEIGHT - top_margin  # Adjust graph height

    # Display PPG graph below the BPM text
    max_sensor_values = max(sensor_values)
    min_sensor_values = min(sensor_values)
    sensor_values_range = max_sensor_values - min_sensor_values
    
    for i in range(len(sensor_values) - 1):
        x0 = i * (DISPLAY_WIDTH - 1) // len(sensor_values)
        x1 = (i + 1) * (DISPLAY_WIDTH - 1) // len(sensor_values)
        y0 = graph_height - 1 - int((sensor_values[i] - min_sensor_values) / sensor_values_range * (graph_height - top_margin))
        y1 = graph_height - 1 - int((sensor_values[i + 1] - min_sensor_values) / sensor_values_range * (graph_height - top_margin))
        oled.line(x0, y0 + top_margin, x1, y1 + top_margin, 1)
    oled.show()


     
#####################################
#  Functions To Calculate HRV Info  #
#####################################
     
     
def meanPPI_calculator(data):
    sumPPI = 0 
    for i in data:
        sumPPI += i
    rounded_PPI = round(sumPPI/len(data), 0)
    return int(rounded_PPI)

def meanHR_calculator(meanPPI):
    rounded_HR = round(60*1000/meanPPI, 0)
    return int(rounded_HR)

def SDNN_calculator(data, PPI):
    summary = 0
    for i in data:
        summary += (i-PPI)**2
    SDNN = (summary/(len(data)-1))**(1/2)
    rounded_SDNN = round(SDNN, 0)
    return int(rounded_SDNN)

def RMSSD_calculator(data):
    i = 0
    summary = 0
    while i < len(data)-1:
        summary += (data[i+1]-data[i])**2
        i +=1
    rounded_RMSSD = round((summary/(len(data)-1))**(1/2), 0)
    return int(rounded_RMSSD)

def SDSD_calculator(data):
    PP_array = []
    i = 0
    first_value = 0
    second_value = 0
    while i < len(data)-1:
        PP_array.append(int(data[i+1])-int(data[i]))
        i += 1
    i = 0
    while i < len(PP_array)-1:
        first_value += float(PP_array[i]**2)
        second_value += float(PP_array[i])
        i += 1
    first = first_value/(len(PP_array)-1)
    second = (second_value/(len(PP_array)))**2
    rounded_SDSD = round((first - second)**(1/2), 0)
    return int(rounded_SDSD)
  
def SD1_calculator(SDSD):
    rounded_SD1 = round(((SDSD**2)/2)**(1/2), 0)
    return int(rounded_SD1)

def SD2_calculator(SDNN, SDSD):
    rounded_SD2 = round(((2*(SDNN**2))-((SDSD**2)/2))**(1/2), 0)
    return int(rounded_SD2)
     


     
####################################
#  Functions To Save/Read History  #
####################################
   
     
def New_History(New_Data):
    Date_Time = utime.localtime()
    year, month, day, hour, minute, _, _, _ = Date_Time
    Date_Time = f"{day}.{month}.{year} {hour}:{minute}"
    f = open('Prev_History.txt','w')
    f.write(Date_Time+New_Data)
    f.close()



def Previous_History():
    History = open('Prev_History.txt','r')
    History_Data = History.read()
    Formated_Data = History_Data.split('\n')
    History.close()
    y = -11
    oled.fill(0)
    for i in Formated_Data:
        y+=11
        oled.text(i,0,y,1)
    oled.show()
          
     
     
###################################
#  Functions To Connect to WLAN   #
###################################
     
def connect_wlan():
    # Connecting to the group WLAN
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    Attempts = 0
    # Attempt to connect once per second
    while wlan.isconnected() == False and Attempts <= 150:
        Attempts +=1
 
def connect_mqtt():
    mqtt_client=MQTTClient("", BROKER_IP)
    mqtt_client.connect(clean_session=True)
    return mqtt_client
 


#######################################
#  Assigned Components of Raspberry   #
#######################################



#OLED 
i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)

#Encoder
encoder = RotaryEncoder(10, 11, 12, 300)

#Menu Display
led_onboard = Pin("LED", Pin.OUT)
led_onboard.off()
menu_display = MenuDisplay(oled,led_onboard)

#sw_0 And sw_2 Buttons
On_btn = Pin(7,Pin.IN, Pin.PULL_UP)
KG_btn= Pin(9,Pin.IN, Pin.PULL_UP)

#Custom Made Heart and Line Using Bitmap
heart = framebuf.FrameBuffer(Heart_Empty.img, 32, 32, framebuf.MONO_VLSB)
line = framebuf.FrameBuffer(line.img, 127, 32, framebuf.MONO_VLSB)

#ADC
adc = machine.ADC(0)



##################################################
#  Used To Connect To the Modem for using MQTT   #
##################################################


SSID = "KME761_Group_13"
PASSWORD = "KME761_Group_13!"
BROKER_IP = "192.168.13.253"


##################################
#  Kubios API, Login, And URI    #
##################################


APIKEY = "pbZRUi49X48I56oL1Lq8y8NDjq6rPfzX3AQeNo3a" 
CLIENT_ID = "3pjgjdmamlj759te85icf0lucv" 
CLIENT_SECRET = "111fqsli1eo7mejcrlffbklvftcnfl4keoadrdv1o45vt9pndlef" 
LOGIN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/login" 
TOKEN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/oauth2/token" 
REDIRECT_URI = "https://analysis.kubioscloud.com/v1/portal/login"


####################################
#  Assigned States and Variables   #
####################################

start_state = True
begining = True
collect_state=True
work_state=True
sensor_values = []
PPI = []
Timer = machine.Timer(-1)


    ###############
    #  Main Loop  #   
    ###############


while True:
    if (On_btn.value() == 0 or KG_btn.value()== 0) and start_state: #Turn On Machine
        if begining: #If It Begins From Begining
            menu_display.Welcome_Text()
            encoder.current_row = 0
            begining = False
        menu_display.update()
        encoder.Menu_state = True
        while encoder.Menu_state:
            
            ###################
            # Choosing Option #
            ###################
            
            while encoder.Rotation.has_data():
                rotation_action = encoder.Rotation.get()
                if rotation_action == 1: 
                    menu_display.next_opt()
                elif rotation_action == 0:  
                    menu_display.prev_opt()
                elif encoder.pin_sw.value() == 0:  
                    menu_display.toggle_opt()
                    
                            ###############
                            # HRV Options #
                            ###############
                    
                    if menu_display.options_state == "HRV" or menu_display.options_state == "Kubios HRV":
                        encoder.Menu_state = False
                        menu_display.Press_Start()
                        time.sleep(0.5)
                        while work_state:
                            if encoder.pin_sw.value() == 0:
                                time.sleep(0.5)
                                oled.fill(0)
                                oled.text("Calculating ",20,26,1)
                                oled.text("BPM..",49,36,1)
                                oled.show()
                                
                                
                                ##################################
                                # Collecting ADC And Finding BPM #
                                ##################################
                                
                                while collect_state:
                                        collect_state = collect_values() #Keeps Going Till Button Is Pressed
                                        
                                work_state = False
                        
                        Timer.deinit()
                        oled.fill(0)
                        
                        
                                ########################
                                # Normal HRV With MQTT #
                                ########################
                        
                        if PPI and menu_display.options_state == "HRV":
                            
                            
                            ###################################
                            # Calculating The Analysis Values #
                            ###################################
                            
                            mean_PPI = meanPPI_calculator(PPI)                            
                            mean_HR = str(int(meanHR_calculator(mean_PPI)))                            
                            SDNN = SDNN_calculator(PPI, mean_PPI)
                            RMSSD = str(int(RMSSD_calculator(PPI)))        
                            SDSD = SDSD_calculator(PPI)
                            SD1 = str(int(SD1_calculator(SDSD)))
                            SD2 = str(int(SD2_calculator(SDNN, SDSD)))
                            
                            #Converting Them To String To Display It
                            mean_PPI = str(int(mean_PPI))
                            SDNN = str(int(SDNN))
                            SDSD = str(int(SDSD))
                            
                            
                            #Calls Function To Display The Info
                            menu_display.Show_Info(menu_display.options_state,mean_PPI,mean_HR,SDNN,RMSSD,SD1,SD2)                    
                           
                            PPI.clear() #Clears Peak-to-Peak Intervals
                            
                            time.sleep(0.5)
                            
                            #####################
                            # Press To Continue #
                            #####################
                            
                            while True:
                                if encoder.pin_sw.value() == 0:
                                    break
                            
                            ############################
                            # Do You Want To Save Text #
                            ############################
                                                        
                            menu_display.Save_Info_Text()
                            
                            #####################
                            # Save The HRV Info #
                            #####################
    
                            while True:
                                # Yes, Save
                                if On_btn.value() == 0:
                                    Data_Saved = f"\nMeanPPI:{mean_PPI}ms\nMeanHR:{mean_HR}bpm\nSDNN:{SDNN}ms\nRMSSD:{RMSSD}ms\nSD1:{SD1} SD2:{SD2}"    
                                    New_History(Data_Saved)
                                    oled.fill(0)
                                    oled.text("History Has Been",0,25,1)
                                    oled.text("Updated!!!",24,35,1)
                                    oled.show()
                                    time.sleep(1)
                                    break
                                
                                #No, Donot Save
                                if KG_btn.value() == 0:
                                    break
                            
                                ####################
                                # MQTT Server Part #
                                ####################
                            
                            oled.fill(0)
                            oled.text("Sending Info to ",0,28,1)
                            oled.text("The Server... ",10,38,1)
                            oled.show()
                            
                            time.sleep(1.25)
                            
                            connect_wlan()

                            try:
                                #Try To Connect
                                mqtt_client=connect_mqtt()
                                try:
                                
                                    # Sending Info Of Analysis by MQTT.
                                    topic = "HRV_Info"
                                    Info = ['MeanPPI:'+ mean_PPI +'ms','MeanHR:'+ mean_HR +'bpm',
                                            'SDNN:'+ SDNN +'ms','RMSSD:'+ RMSSD +'ms',
                                            'SD1:'+ SD1 +' SD2:'+ SD2]
                                    for i in Info:
                                        mqtt_client.publish(topic, i)
                                    Space = "---------------"
                                    mqtt_client.publish(topic, Space)
                                    oled.fill(0)
                                    oled.text("The Infomation",0,28,1)
                                    oled.text("Has Been Sent!!!",0,38,1)
                                    oled.show()
                                    time.sleep(2)
                                                                   
                                        
                                except Exception as e:
                                    #Unable To Send Info
                                    oled.fill(0)
                                    oled.text("Unable to Send",0,17,1)
                                    oled.text("Info,Try Again ",0,27,1)
                                    oled.text("Later Please...",0,37,1)
                                    oled.show()
                            
                                
                            except Exception as e:
                                #Unable To Connect
                                oled.fill(0)
                                oled.text("Connection Could",0,17,1)
                                oled.text("Not be Made, Try",0,27,1)
                                oled.text("Again Later..",0,37,1)
                                oled.show()
                                time.sleep(2)
                          
                            
                            ##########################
                            # HRV Using Kubios Cloud #
                            ##########################
                            
                        elif len(PPI) >= 10 and menu_display.options_state == "Kubios HRV":
                            oled.text("Analyzing PPI",0,12,1)
                            oled.text("Using The Kubios",0,22,1)
                            oled.text("Cloud Server",0,32,1)
                            oled.text("Please Wait...",0,52,1)
                            oled.show()
                            time.sleep(1.25)
                            
                                    
                                #############################
                                # Using Response For Kubios #
                                #############################
                            
                            
                            try:
                                response = requests.post(
                                    url = TOKEN_URL, 
                                    data = 'grant_type=client_credentials&client_id={}'.format(CLIENT_ID), 
                                    headers = {'Content-Type':'application/x-www-form-urlencoded'}, 
                                    auth = (CLIENT_ID, CLIENT_SECRET)
                                )
                                
                                response_json = response.json()  # Parse JSON response into a python dictionary 
                                access_token = response_json["access_token"]  # Parse access token
                                HRV_Info= {
                                    "type": "RRI",
                                    "data": PPI,
                                    "analysis": {"type": "readiness"}
                                }
                                
                                # Make the readiness analysis with the given data
                                response = requests.post(
                                    url = "https://analysis.kubioscloud.com/v2/analytics/analyze",
                                    headers = {"Authorization": "Bearer {}".format(access_token), "X-Api-Key": APIKEY},
                                    json = HRV_Info
                                )
                                
                                #Get The Response and Make It A Nested Dictonary
                                response = response.json()
                                
                                
                                # Done To Make It Easier To Display And Save
                                mean_PPI = str(int(response["analysis"]["mean_rr_ms"]))
                                mean_HR =  str(int(response["analysis"]["mean_hr_bpm"]))
                                SDNN = str(int(response["analysis"]["sdnn_ms"]))
                                RMSSD =str(int(response["analysis"]["rmssd_ms"]))
                                SNS =str(int(response["analysis"]["sns_index"]))
                                PNS =str(int(response["analysis"]["pns_index"]))
                                
                                #Display The Data On The OLED
                                menu_display.Show_Info(menu_display.options_state,mean_PPI,mean_HR,SDNN,RMSSD,SNS,PNS)                              
                                
                                #Clear The PPI Valuse
                                PPI.clear()
                                
                                time.sleep(0.5)
                                
                                #####################
                                # Press To Continue #
                                #####################
                                
                                while True:
                                    if encoder.pin_sw.value() == 0:
                                        break
                                
                                ############################
                                # Do You Want To Save Text #
                                ############################
                                
                                menu_display.Save_Info_Text()
                                
                                #####################
                                # Save The HRV Info #
                                #####################
                                
                                while True:
                                    # Yes, Save
                                    if On_btn.value() == 0:
                                        Data_Saved = f"\nMeanPPI:{mean_PPI}ms\nMeanHR:{mean_HR}bpm\nSDNN:{SDNN}ms\nRMSSD:{RMSSD}ms\nSNS:{SNS} PNS:{PNS}"    
                                        New_History(Data_Saved)
                                        oled.fill(0)
                                        oled.text("History Has Been",0,25,1)
                                        oled.text("Updated!!!",24,35,1)
                                        oled.show()
                                        time.sleep(1)
                                        break
                                    
                                    #No, Donot Save
                                    if KG_btn.value() == 0:
                                        break
                                    
                                    
                    #######################################
                    # Incase Connection Could Not Be Made #
                    #######################################
                                
                            except:
                                oled.fill(0)
                                oled.text("Connection Could",0,17,1)
                                oled.text("Not be Made, Try",0,27,1)
                                oled.text("Again Later..",0,37,1)
                                oled.show()
                                time.sleep(2)
                                                  
                           
                    ##################################################
                    # Interupting before A Single PPI Could Be Found #
                    ##################################################
                        
                        elif not PPI:
                            oled.text("The Process Was",0,17,1)
                            oled.text("Stopped, Going ",0,27,1)
                            oled.text("Back To The Menu",0,37,1)
                            oled.show()
                            time.sleep(2)
                                
                    #####################################################
                    # Reseting States For Menu, Working, and ADC Values #
                    #####################################################
                        
                        menu_display.options_state = ""
                        time.sleep(0.5)
                        encoder.Menu_state = True
                        work_state = True
                        collect_state=True
                        menu_display.update()
                        
                        
                        
                        #################################
                        # Want To View Previous History #
                        #################################
                        
                    
                    elif menu_display.options_state == "History":
                        oled.fill(0)
                        oled.text("Retrieving The",0,25,1)
                        oled.text("Previous Info...",0,35,1)
                        oled.show()
                        time.sleep(1.7)                       
                        Previous_History()
                        
                         #####################
                        # Press To Continue #
                        #####################
                        
                        while True:
                            if encoder.pin_sw.value() == 0:
                                break
                        
                        time.sleep(0.7)
                   
                            ##########################
                            # Turning Off The Device # 
                            ##########################
                    
                    elif menu_display.options_state == "Exit":
                        encoder.Menu_state = False
                        oled.fill(0)
                        oled.show()
                        oled.text("Do You Want To",0,0,1)
                        oled.text("Turn Off Device?",0,9,1)
                        
                        # Turns Off The Device
                        oled.text("SW_2 = Yes",0,28,1)
                        oled.text("SW_0 = No",0,38,1)
                        menu_display.options_state = ""
                        oled.show()
                        
                        
                        #####################################
                        # Conformation Of Turning Of Device #
                        #####################################
                        
                        while True:
                            # Yes, Turn Off
                            if On_btn.value() == 0:
                                begining=True
                                menu_display.current_row = 0
                                menu_display.GoodBye()
                                break
                            
                            #No, Got Back To Menu
                            if KG_btn.value() == 0:
                                work_state = True
                                menu_display.update()
                                break
                        start_state = True
                        
                    
    ############################################################
    # Checking States and Making sure to go to the right place #
    ############################################################
                    if not encoder.Menu_state:
                        break
                menu_display.update()
                if begining:
                    break
            if begining:
                break         
