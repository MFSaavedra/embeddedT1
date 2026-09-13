idf_component_register(
    SRCS "main.c"
         "protocol.c"
         "uart_link.c"
         "commands.c"
         "accel_sim.c"
         "env_sim.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_driver_uart esp_timer esp_hw_support vfs
)
