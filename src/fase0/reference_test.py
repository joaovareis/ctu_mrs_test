#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
import time
import math

# Modificado para incluir a mensagem e o serviço de Reference corretos
from mrs_msgs.msg import ReferenceStamped, Reference
from mrs_msgs.srv import ReferenceStampedSrv, String as MrsString
from std_srvs.srv import Trigger

#O fast funciona aqui também, vai entender. Ele é brutalmente rapido. Não usar no mundo real.
#Evitar usar o reference para longas trajetórias por que ele faz o drone se mover como se tivesse em alto-mar e pode causar trancos
#Usar ele somente para ajuste fino de posição, como centralizar algo


class MRSReferenceMissionClient(Node):
    def __init__(self):
        super().__init__('mrs_reference_mission_client')
        
        # Garante o sincronismo de tempo com o simulador (Gazebo)
        self.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        
        # Cliente para mudar a velocidade (Constraints)
        self.constraints_client = self.create_client(MrsString, '/uav1/constraint_manager/set_constraints')
        
        # Cliente do SET REFERENCE
        self.reference_client = self.create_client(ReferenceStampedSrv, '/uav1/control_manager/reference')
        
        # Cliente do UAV Manager para o pouso
        self.land_client = self.create_client(Trigger, '/uav1/uav_manager/land')
        
        self.get_logger().info('Aguardando conexão com os serviços do MRS...')
        self.constraints_client.wait_for_service()
        self.reference_client.wait_for_service()
        self.land_client.wait_for_service()
        
    def change_speed(self, profile_name):
        self.get_logger().info(f'Alterando perfil de velocidade para: {profile_name}')
        req = MrsString.Request()
        req.value = str(profile_name)
        self.constraints_client.call_async(req)

    def enviar_e_executar_goto(self, x, y, z, heading_graus=0.0, tempo_voo_estimado=15.0):
        """Envia uma referência direta de posição (Goto) para o Control Manager"""
        req = ReferenceStampedSrv.Request()
        
        # Monta a estrutura da mensagem de referência
        p = Reference()
        p.position.x = float(x)
        p.position.y = float(y)
        p.position.z = float(z)
        p.heading = float(math.radians(heading_graus)) # Convertendo o Yaw para Radianos!
        
        req.reference = p
        
        self.get_logger().info(f'Chamando set_reference para a coordenada: ({x}, {y}, {z}) com Yaw: {heading_graus}°')
        
        future = self.reference_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        
        if future.result() and future.result().success:
            # Como o 'set_reference' não avisa quando chega no ponto (ele só avisa que aceitou o comando),
            # precisamos esperar o tempo estimado de voo para o drone fisicamente se deslocar até lá.
            self.get_logger().info(f'Deslocando-se para o ponto... Aguardando {tempo_voo_estimado}s')
            time.sleep(tempo_voo_estimado)
            return True
        else:
            self.get_logger().error('O Control Manager rejeitou o comando Reference.')
            return False

    def executar_missao(self):
        # Lista de coordenadas solicitadas: (x, y, z)
        coordenadas = [
            (2.0, 6.0, 2.5, 'slow', 0.0),
            (-2.5, 0.0, 2.5, 'fast', 90.0),
            (2.0, -5.0, 2.5, 'medium', 0)
        ]
        
        # Rodando os mesmos 3 pontos. 
        for i, (x, y, z, r, yaw) in enumerate(coordenadas, 1):
            self.get_logger().info(f'--- Iniciando Ponto {i} ---')
                        
            self.change_speed(r)
            sucesso = self.enviar_e_executar_goto(x, y, z, heading_graus=yaw, tempo_voo_estimado=15.0)
            
            if sucesso:
                self.get_logger().info(f'Drone estabilizado na posição {i}. Pausando por 10 segundos...')
                time.sleep(5.0)
            else:
                self.get_logger().error(f'Missão abortada devido a falha no ponto {i}.')
                return

        # --- FIM DA MISSÃO: POUSAR ---
        self.get_logger().info('--- Todas as coordenadas concluídas. Iniciando o pouso automático... ---')
        req_land = Trigger.Request()
        future_land = self.land_client.call_async(req_land)
        rclpy.spin_until_future_complete(self, future_land)
        
        if future_land.result() and future_land.result().success:
            self.get_logger().info('Comando de pouso (Land) executado. Fim!')
        else:
            self.get_logger().error('O UAV Manager rejeitou o comando de pouso.')

def main(args=None):
    rclpy.init(args=args)
    node = MRSReferenceMissionClient()
    node.executar_missao()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()