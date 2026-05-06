import network
from machine import SPI, Pin

def SetUpWiznetChip():
    NET_IP   = "10.0.1.109"
    NET_SN   = "255.255.255.0"
    NET_GW   = "10.0.1.254"
    NET_DNS  = "8.8.8.8"

    spi = SPI(2, baudrate=8_000_000, polarity=0, phase=0)

    cs  = Pin("PB12", Pin.OUT)
    rst = Pin("PD9", Pin.OUT)
    pwn = Pin("PE15", Pin.OUT, value =0)

    nic = network.WIZNET5K(spi, cs, rst)

    # Reset the WIZnet chip
    nic.active(True)

    # Please use your PC to Ping "192.168.1.20"
    try:
        print('==== Assigning DHCP ====')
        nic.ifconfig("dhcp")
    except Exception as e:
        print('==== Failure in DHCP. Try Static IP instead ====')
        print('IP at ', NET_IP)
        nic.ifconfig((NET_IP, NET_SN, NET_GW, NET_DNS))
    print('Your IP is : ', nic.ifconfig()[0])
    return nic