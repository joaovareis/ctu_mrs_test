#!/usr/bin/env python3

import time
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from mrs_msgs.srv import Vec4, String as MrsString
from std_srvs.srv import Trigger, SetBool

class MrsMapSquare(Node):

    def __init__(self):
        super().__init__('mrs_direct_square_node')
        
        self.set_parameters([rclpy.parameter.Parameter('use_sim_time', rclpy.Parameter.Type.BOOL, True)])
        
        cb_group_clients = MutuallyExclusiveCallbackGroup()
        cb_group_mission = MutuallyExclusiveCallbackGroup()
        
        # Clientes de Navegação
        self.goto_absolute_client = self.create_client(Vec4, '/uav1/control_manager/goto', callback_group=cb_group_clients)
        self.set_constraints_client = self.create_client(MrsString, '/uav1/constraint_manager/set_constraints', callback_group=cb_group_clients)
        self.land_client = self.create_client(Trigger, '/uav1/uav_manager/land', callback_group=cb_group_clients)
        
        # Clientes de Gerenciamento e Firmware
        self.arm_client = self.create_client(SetBool, '/uav1/hw_api/arming', callback_group=cb_group_clients)
        self.enable_callbacks_client = self.create_client(SetBool, '/uav1/control_manager/enable_callbacks', callback_group=cb_group_clients)
        self.midair_client = self.create_client(Trigger, '/uav1/uav_manager/midair_activation', callback_group=cb_group_clients)
        self.takeoff_client = self.create_client(Trigger, '/uav1/uav_manager/takeoff', callback_group=cb_group_clients)
        
        self.mission_started = False
        self.timer = self.create_timer(1.0, self.init_mission_callback, callback_group=cb_group_mission)

    def init_mission_callback(self):
        if self.mission_started:
            return
        self.mission_started = True
        self.timer.cancel()
        self.run_mission()

    def run_mission(self):
        self.get_logger().info('Verificando a disponibilidade dos serviços da MRS...')
        
        while rclpy.ok():
            if (self.goto_absolute_client.wait_for_service(timeout_sec=0.1) and
                self.set_constraints_client.wait_for_service(timeout_sec=0.1) and
                self.land_client.wait_for_service(timeout_sec=0.1) and
                self.arm_client.wait_for_service(timeout_sec=0.1) and
                self.enable_callbacks_client.wait_for_service(timeout_sec=0.1) and
                self.midair_client.wait_for_service(timeout_sec=0.1) and
                self.takeoff_client.wait_for_service(timeout_sec=0.1)):
                break
            time.sleep(0.5)
                
        self.get_logger().info('Sucesso! Todos os serviços conectados.')
        time.sleep(1.0) 

        # ====== 1. CONFIGURAR PERFIL INICIAL ======
        self.change_speed('slow')
        time.sleep(0.5)

        # ====== 2. ATIVAR CALLBACKS ======
        self.get_logger().info('Ativando as saídas de controle (enable_callbacks)...')
        req_callbacks = SetBool.Request()
        req_callbacks.data = True
        self.enable_callbacks_client.call_async(req_callbacks)
        time.sleep(1.5) 

        # ====== 3. ARMAR MOTORES ======
        self.get_logger().info('Armando os motores via HW API...')
        req_arm = SetBool.Request()
        req_arm.data = True
        self.arm_client.call_async(req_arm)
        time.sleep(2.0) 

        # ====== 4. ATIVAÇÃO INTEGRADA ======
        # Resolve o travamento do Offboard injetando o fluxo de controle automaticamente
        self.get_logger().info('Invocando o midair_activation para forçar modo Offboard...')
        req_midair = Trigger.Request()
        self.midair_client.call_async(req_midair)
        time.sleep(2.5) 

        # ====== 5. DECOLAGEM AUTOMÁTICA ======
        self.get_logger().info('Iniciando rotina de Takeoff...')
        req_takeoff = Trigger.Request()
        self.takeoff_client.call_async(req_takeoff)
        
        self.get_logger().info('Aguardando o drone estabilizar em HOVER (15s)...')
        time.sleep(15.0) 

        # ====== 6. CIRCUITO QUADRADO ======
        self.get_logger().info('Iniciando execução do circuito quadrado...')
        self.change_speed('medium')
        time.sleep(0.5)
        
        self.move_absolute(x=2.0, y=0.0, z=2.5, heading=0.0, desc="Lado 1")
        time.sleep(8.0)

        self.move_absolute(x=2.0, y=2.0, z=2.5, heading=0.0, desc="Lado 2")
        time.sleep(8.0)

        self.move_absolute(x=0.0, y=2.0, z=2.5, heading=0.0, desc="Lado 3")
        time.sleep(8.0)

        self.change_speed('slow')
        time.sleep(0.5)
        self.move_absolute(x=0.0, y=0.0, z=2.5, heading=0.0, desc="Lado 4 (Retorno)")
        time.sleep(8.0)

        # ====== 7. POUSO AUTOMÁTICO ======
        self.get_logger().info('Missão concluída com sucesso! Acionando Land...')
        req_land = Trigger.Request()
        self.land_client.call_async(req_land)

    def move_absolute(self, x, y, z, heading=0.0, desc=""):
        self.get_logger().info(f'Ponto [{desc}] -> X:{x}, Y:{y}, Z:{z}')
        req = Vec4.Request()
        req.goal = [float(x), float(y), float(z), float(heading)]
        self.goto_absolute_client.call_async(req)

    def change_speed(self, profile_name):
        self.get_logger().info(f'Alterando perfil de velocidade para: {profile_name}')
        req = MrsString.Request()
        req.value = str(profile_name)
        self.set_constraints_client.call_async(req)

def main(args=None):
    rclpy.init(args=args)
    drone = MrsMapSquare()
    
    executor = MultiThreadedExecutor()
    executor.add_node(drone)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        drone.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()