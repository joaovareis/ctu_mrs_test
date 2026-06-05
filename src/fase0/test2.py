#!/usr/bin/env python3

import time
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

# Mensagens e Serviços da MRS
from mrs_msgs.srv import Vec4, String as MrsString
from mrs_msgs.msg import ControlManagerDiagnostics
from std_srvs.srv import Trigger

class MrsMapSquare(Node):

    def __init__(self):
        super().__init__('mrs_direct_square_node')
        
        self.set_parameters([rclpy.parameter.Parameter('use_sim_time', rclpy.Parameter.Type.BOOL, True)])
        
        # Separação de grupos de callback para execução multithread segura
        cb_group_clients = MutuallyExclusiveCallbackGroup()
        cb_group_subs = MutuallyExclusiveCallbackGroup()
        cb_group_mission = MutuallyExclusiveCallbackGroup()
        
        # ====== SUBSCRICAO DE TELEMETRIA (Conexão com o Autostart) ======
        self.flying_normally = False
        self.control_diag_sub = self.create_subscription(
            ControlManagerDiagnostics, 
            '/uav1/control_manager/diagnostics', 
            self.control_diag_callback, 
            10, 
            callback_group=cb_group_subs
        )
        
        # ====== CLIENTES DE NAVEGAÇÃO ======
        # Removeu-se arm_client, takeoff_client, offboard_client, etc., pois o Autostart cuida deles.
        self.goto_absolute_client = self.create_client(Vec4, '/uav1/control_manager/goto', callback_group=cb_group_clients)
        self.set_constraints_client = self.create_client(MrsString, '/uav1/constraint_manager/set_constraints', callback_group=cb_group_clients)
        self.land_client = self.create_client(Trigger, '/uav1/uav_manager/land', callback_group=cb_group_clients)
        
        self.mission_started = False
        self.timer = self.create_timer(1.0, self.init_mission_callback, callback_group=cb_group_mission)

    def control_diag_callback(self, msg):
        # Captura a flag que o nó de autostart usa para saber que o voo estabilizou
        self.flying_normally = msg.flying_normally

    def init_mission_callback(self):
        if self.mission_started:
            return
        self.mission_started = True
        self.timer.cancel()
        self.run_mission()

    def run_mission(self):
        self.get_logger().info('Verificando a disponibilidade dos serviços de navegação da MRS...')
        
        while rclpy.ok():
            if (self.goto_absolute_client.wait_for_service(timeout_sec=0.1) and
                self.set_constraints_client.wait_for_service(timeout_sec=0.1) and
                self.land_client.wait_for_service(timeout_sec=0.1)):
                break
            time.sleep(0.5)
                
        self.get_logger().info('Sucesso! Serviços de navegação conectados.')

        # ====== INTEGRAÇÃO COM O AUTOSTART ======
        self.get_logger().info('Aguardando o nó "automatic_start" realizar os testes pré-voo, armar e decolar...')
        
        # Loop de bloqueio seguro: O script Python espera o sinal verde do Autostart
        while rclpy.ok():
            if self.flying_normally:
                self.get_logger().info('Sinal recebido: Drone está em estado FLYING_NORMALLY. Assumindo controle da missão!')
                break
            time.sleep(1.0)
                
        # Pequena janela de amortecimento para o drone estabilizar completamente em Hover
        time.sleep(2.0) 

        # ====== CIRCUITO QUADRADO ======
        self.get_logger().info('Iniciando execução do circuito quadrado...')
        self.change_speed('medium')
        time.sleep(0.5)
        
        # Alterado para .call() síncrono: garante o envio correto antes de iniciar o contador de tempo
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

        # ====== POUSO AUTOMÁTICO ======
        self.get_logger().info('Missão concluída com sucesso! Acionando Land nativo...')
        req_land = Trigger.Request()
        self.land_client.call(req_land)

    def move_absolute(self, x, y, z, heading=0.0, desc=""):
        self.get_logger().info(f'Ponto [{desc}] -> X:{x}, Y:{y}, Z:{z}')
        req = Vec4.Request()
        req.goal = [float(x), float(y), float(z), float(heading)]
        self.goto_absolute_client.call(req)

    def change_speed(self, profile_name):
        self.get_logger().info(f'Alterando perfil de velocidade para: {profile_name}')
        req = MrsString.Request()
        req.value = str(profile_name)
        self.set_constraints_client.call(req)

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