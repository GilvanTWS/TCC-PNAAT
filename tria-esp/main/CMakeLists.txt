idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES
        conveyor
        tria_actuator
        tria_display
        tria_network
        vibration
)
