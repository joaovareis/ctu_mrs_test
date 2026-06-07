#!/usr/bin/python3
import math
import os
import time
import numpy as np

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

                print("ESTADO - TakeOff")
                
                print("Iniciando procedimentos de decolagem...")
                
                if self.navigateArm():
                    time.sleep(0.1)
                    if self.navigateOffboard():
                        time.sleep(30)
                        print("TakeOff Complete")

                        self.current_state = ''
                        self.fsm.add('TakeOff_complete')

                    else:

                        self.get_logger().error("Falha ao entrar em modo Offboard na decolagem.")
                else:

                    self.get_logger().error("Falha ao armar os motores na decolagem.")

        if self.fsm == 'Forward':
            self.current_state = 'Forward'
            print("ESTADO - Forward")
            
            print("Iniciando sequencia de movimentos na grade...")
            
            # Movimento 1: 2 metros para frente
            self.navigateTrajectory(x=2.0, y=0.0, z=0.0, yaw=0.0, speed='slow', frame='uav1/fcu_untilted')
            time.sleep(5.0)
            
            # Movimento 2: 4 metros para trás
            self.navigateTrajectory(x=2.0, y=2.0, z=2.5, yaw=0.0, speed='slow', frame='uav1/fixed_origin')
            time.sleep(5.0)
            
            # Movimento 3: 2 metros para frente (retorna ao centro)
            self.navigateTrajectory(x=0.0, y=2.0, z=2.5, yaw=0.0, speed='slow', frame='uav1/fixed_origin')
            time.sleep(5.0)
            
            # Movimento 4: 2 metros para a esquerda/direita (depende da convenção do eixo Y local)
            self.navigateTrajectory(x=0.0, y=0.0, z=2.5, yaw=0.0, speed='slow', frame='uav1/fixed_origin')
            time.sleep(5.0)

            print("Movimentacao Forward Complete")     

            self.current_state = ''
            self.fsm.add('Forward_complete')

        if self.fsm == 'Land':
            self.current_state = 'Land'
            print("Iniciando pouso programado...")
            
            self.land()
            
            print("ACABOU - LAND FINAL")
            
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
    
    print("Aguardando chamada do servico ~/start_phase para iniciar a missao...")
    
    try:
        while rclpy.ok():
            mestre.update()
            
            if mestre.fsm == 'Finish':
                print("Máquina de estados detectou o fim da missão. Encerrando o nó mestre...")
                break
                
            time.sleep(0.05)
            executor.spin_once(timeout_sec=0.01)
            
    except KeyboardInterrupt:
        print("Master finalizado manualmente pelo usuario.")

    finally:

        print("Finalizando componentes do ROS 2...")
        mestre.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()