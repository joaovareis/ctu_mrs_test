# ctu_mrs_test
Testing for mru-configuration

Rodar o start.sh na pasta tmux para iniciar a simulação;

Para alternar entre terminais na sessão, utilizar Shift+setas;
Para quitar 'ctrl + a' e depois 'k' (deve aparecer uma janelinha amarela -> 'enter')

Para iniciar a fsm digite: "ros2 service call /master_node/start_phase std_srvs/srv/Trigger {}" em algum terminal do tmux

Se tudo estiver correto, o drone vai levantar voo, completar um quadrado e pousar. 

A fazer:

- Traduzir a maquina de estados pro ROS2/MRS;

-> *Máquina traduzida e Navigate Trajectory finalizado. Falta fazer:*

- Método takeoff no tools que não dependa de um timer
- Navigate Reference
- Verificar serviços para interromper trajetória/referência
- Comentar o código explicando para usuários futuros

- Implementar flags pro start.sh (fases diferentes, rosbag, etc)

- Descobrir uma maneira melhor de dar start_phase

- Fazer o carcará custom -> Adicionar sensor térmico (existe)
