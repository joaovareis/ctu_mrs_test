#!/usr/bin/env python3

import time
import threading
import rclpy
from rclpy.node import Node
from mrs_msgs.srv import Vec4, String as MrsString
from std_srvs.srv import Trigger # Importado para o comando de Land (pouso)
from nav_msgs.msg import Odometry
import math


#--------
#As velocidades aceitas são "slow", "medium" e "fast". Mas o fast não rola por que a odometria não é boa o suficiente na simulação.
#Tem como melhorar ela publicando opt.flow ou rtk mas meu foco por enquanto é ter um pacote funcional (isso envolveria fazer um drone custom)
#Fazer o carcara parece facil pelo tutorial deles mas eu tomei um gap pra criar um sensor.

#Ainda é necessário adicionar multithreaded executors e Mutually exclusive callback groups, mas isso é papo pra FSM potente;
#Esse é apenas uma demo com um "navigate" do body, map e a telemetria
#O correto seria implementar o Trajectory ao invés do go-to, mas por hoje é o suficiente


class MrsFcuSquare(Node):

    def __init__(self):
        super().__init__('mrs_direct_square_node', namespace='uav1')
        
        # Clientes de serviço (utilizando nomes relativos ao namespace /uav1 do nó)
        self.goto_fcu_client = self.create_client(Vec4, 'control_manager/goto_fcu')
        self.goto_client = self.create_client(Vec4, '/uav1/control_manager/goto')
        self.land_client = self.create_client(Trigger, 'uav_manager/land') # Cliente do Land
        self.set_constraints_client = self.create_client(MrsString, '/uav1/constraint_manager/set_constraints')

        self.odom_sub = self.create_subscription(
            Odometry,
            '/uav1/estimation_manager/odom_main',
            self.odom_callback,
            10
        )
        
        self.mission_thread = threading.Thread(target=self.run_mission)
        self.mission_thread.start()

    def odom_callback(self, msg):
        # 1. Posição (X, Y, Z) em relação ao frame de origem (Map)
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        z = msg.pose.pose.position.z

        # 2. Orientação (Convertendo Quaternion para Yaw em radianos)
        q = msg.pose.pose.orientation
        # Fórmula de conversão Quaternion para Yaw (Euler Z)
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        self.telem = (f'Telemetria -> X: {x:.2f} | Y: {y:.2f} | Z: {z:.2f} | Yaw: {math.degrees(yaw):.1f}°')

    def run_mission(self):
        self.get_logger().info('Aguardando serviços ficarem ativos (goto_fcu e land)...')
        # Garante que ambos os serviços necessários estejam prontos no ecossistema
        while not self.goto_fcu_client.wait_for_service(timeout_sec=2.0) or not self.land_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('Ainda aguardando serviços...')
            if not rclpy.ok():
                return
                
        self.get_logger().info('Serviços conectados! Iniciando sequência de voo...')
        time.sleep(8.0)

        self.navigate_map(x=0.0, y=0.0, z=2.5, yaw=0.0, desc="Subida Inicial")
        time.sleep(10.0) 

        # Lado 1: Avança 2 metros para a frente
        self.change_speed('slow')
        print(self.telem)
        self.navigate_body(x=2.0, y=0.0, z=0.0, yaw=0.0, desc="Lado 1: Frente 2m")
        time.sleep(7.0)

        # Lado 2: Move 2 metros para a esquerda
        self.change_speed('medium')
        print(self.telem)
        self.navigate_body(x=0.0, y=2.0, z=0.0, yaw=0.0, desc="Lado 2: Esquerda 2m")
        time.sleep(7.0)

        # Lado 3: Recua 2 metros
        self.change_speed('slow')
        print(self.telem)
        self.navigate_body(x=-2.0, y=0.0, z=0.0, yaw=0.0, desc="Lado 3: Trás 2m")
        time.sleep(7.0)

        # Lado 4: Move 2 metros para a direita (Fecha o quadrado)
        self.change_speed('medium')
        print(self.telem)
        self.navigate_body(x=0.0, y=-2.0, z=0.0, yaw=0.0, desc="Lado 4: Direita 2m")
        time.sleep(7.0)

        # 3. Procedimento de Pouso Automático
        self.get_logger().info('Quadrado concluído! Iniciando procedimento de pouso (Land)...')
        req_land = Trigger.Request()
        
        future_land = self.land_client.call_async(req_land)
        
        # Aguarda a confirmação de recebimento do comando de pouso
        while rclpy.ok() and not future_land.done():
            time.sleep(0.1)
            
        self.get_logger().info('Comando de Land aceito pelo uav_manager. O drone está pousando!')

    def navigate_body(self, x, y, z, yaw, desc=""):
        self.get_logger().info(f'Enviando [{desc}] -> X:{x}, Y:{y}, Z:{z}')
        req = Vec4.Request()
        req.goal = [float(x), float(y), float(z), float(yaw)]
        
        future = self.goto_fcu_client.call_async(req)
        while rclpy.ok() and not future.done():
            time.sleep(0.05)

    def navigate_map(self, x, y, z, yaw, desc=""):
        self.get_logger().info(f'Enviando [{desc}] -> X:{x}, Y:{y}, Z:{z}')
        req = Vec4.Request()
        req.goal = [float(x), float(y), float(z), float(yaw)]
        
        future = self.goto_client.call_async(req)
        while rclpy.ok() and not future.done():
            time.sleep(0.05)

    def change_speed(self, profile_name):
        self.get_logger().info(f'Alterando perfil de velocidade para: {profile_name}')
        req = MrsString.Request()
        req.value = str(profile_name)
        self.set_constraints_client.call_async(req)

def main(args=None):
    rclpy.init(args=args)
    drone = MrsFcuSquare()
    try:
        rclpy.spin(drone)
    except KeyboardInterrupt:
        pass
    drone.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()