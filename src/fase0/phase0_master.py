#!/usr/bin/python3
import math
import os
import time
import numpy as np
import colorful as cf

import rclpy
from tools_node import Tools
from states import *

class Master(Tools):
    def __init__(self) -> None:
        super().__init__(node_name='master_node')

    def update(self):

        if self.fsm == 'TakeOff':
            self.current_state = 'TakeOff'
            if self.start_phase:
                print(cf.magenta("ESTADO - TakeOff"))
                
                print(cf.blue("Iniciando procedimentos de decolagem..."))
                
                self.navigateTakeoff()
                time.sleep(2.0)

                print(cf.magenta("TakeOff Complete"))

                self.current_state = ''
                self.fsm.add('TakeOff_complete')

        if self.fsm == 'Forward':
            self.current_state = 'Forward'
            print(cf.magenta("ESTADO - Forward"))

            #Instruções sobre métodos no tools em suas respectivas definições.
                        
            self.navigateTrajectory(x=2.0, y=0.0, z=2.5, yaw=(math.pi/2), speed='slow', frame='uav1/local_origin')
            time.sleep(2.0)
            
            self.navigateReference(x=2.0, y=0.0, z=0.0, yaw=(math.pi/2), speed='slow', frame='uav1/fcu_untilted')
            time.sleep(2.0)
            
            self.navigateTrajectory(x=0.0, y=2.0, z=2.5, yaw=0.0, speed='slow', frame='uav1/fixed_origin')
            time.sleep(2.0)
            
            self.navigateTrajectory(x=0.0, y=0.0, z=2.5, yaw=0.0, speed='slow', frame='uav1/fixed_origin')
            time.sleep(2.0)

            print(cf.magenta("Forward Complete"))     

            self.current_state = ''
            self.fsm.add('Forward_complete')

        if self.fsm == 'Land':
            self.current_state = 'Land'
            print(cf.magenta("ESTADO - Land"))

            print(cf.yellow("Iniciando pouso"))
            
            self.land()
            
            print(cf.magenta("ACABOU - LAND FINAL"))
            
            self.current_state = ''
            self.fsm.add('finished')
            
        if self.fsm != self.current_state:
            self.fsm.updateEvent() 


def main(args=None): 
    rclpy.init(args=args)
    
    mestre = Master()
    mestre.setSubscribers()
    mestre.setPublishers()
    mestre.setClients()
    mestre.setServer()
    
    executor = rclpy.executors.MultiThreadedExecutor(num_threads=4)
    executor.add_node(mestre)
    
    print(cf.yellow("Aguardando chamada do servico ~/start_phase para iniciar a missao..."))
    
    try:
        while rclpy.ok():
            mestre.update()
            
            if mestre.fsm == 'Finish':
                print(cf.yellow("Máquina de estados encerrada"))
                break
                
            time.sleep(0.05)
            executor.spin_once(timeout_sec=0.01)
            
    except KeyboardInterrupt:
        print(cf.yellow("Master finalizado manualmente pelo usuario."))

    finally:

        print(cf.yellow("Finalizando componentes do ROS 2"))
        mestre.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()