Ideas are cheap, excution is everything.

systemctl status bluetooth
bluetoothctl devices
bluetoothctl info
현재 블루투스 연결된 장치 보기
bluetoothctl info | grep Connected

스피커 테스트
speaker-test -t wav

mplayer cdda:// -cache 4096 -cache-min 20 -ao alsa
mplayer -quiet cdda:// -cache 8192 -cache-min 20 -ao alsa

펄스오디오 싱크에서 볼륨 올리기 +5
pactl set-sink-volume bluez_sink.00_1D_DF_B0_4D_25.a2dp_sink +5%

펄스오디오(스피커 MAC주소) 싱크 음소거/해제
pactl set-sink-mute bluez_sink.00_1D_DF_B0_4D_25.a2dp_sink 1
pactl set-sink-mute bluez_sink.00_1D_DF_B0_4D_25.a2dp_sink 0


기본 음량 조정
pactl set-sink-volume @DEFAULT_SINK@ +5%


http://192.168.219.1/main.asp

RasberryPi: MAC: DC:A6:32:B2:48:10, 고정IP: 192.168.219.150
갤20울트라:  MAX F0:F5:64:63:0F:6A, 고정IP: 192.168.219.151
Desktop Wife: 58:86:94:FD:B8:6C 고정IP: 192.168.219.152
갤탭: Mac 54:DD:4F:6E:CB:A6, 192.168.219.153
갤23S(이슬) 6C:AC:C2:DD:B1:28 192.168.219.154

장치	신호	GPIO	물리 핀
1602A LCD (I2C)	VCC	3.3V	Pin 1
	GND	GND	Pin 6
	SDA	GPIO2 (SDA1)	Pin 3
	SCL	GPIO3 (SCL1)	Pin 5
DHT11	VCC	3.3V	Pin 17
	DATA	GPIO4	Pin 7
	GND	GND	Pin 9
VS1838B (IR)	VCC	3.3V	Pin 1 (공유 가능)
	OUT	GPIO18	Pin 12
	GND	GND	Pin 14
	
	
	
	
ir 수신기 vs1838b 왼쪽부터 [data-gpio18, gnd, 5v] 3.3볼트 안됨
 sudo nano /boot/firmware/config.txt (우분투 기준이고 다른 os에서는 /boot/config.txt 일수도 있음. 둘중 있는걸로)
 에서 마지막줄에 추가후 부팅 [all] 섹션에
 dtoverlay=gpio-ir,gpio_pin=18 
 ls -l /dev/lirc* <-- 나와야함.
   예) crw-rw---- 1 root video 247, 0  8월 27 00:23 /dev/lirc0
 테스트 방법
 sudo apt install -y evtest
 update 이후
 sudo apt-get install ir-keytable -y
 
 ir-keytable 입력해서 ir 장치 번호 알아야함 rc0, rc1, rc2일수 있음.
 sudo ir-keytable -s rc2 -p all  (모든 프로토콜 권한 지정. rc2일때)
 
 
 sudo evtest
 ir-keytable -s rc2 -p all  <-- 이전거 삭제
 ir-keytable -c  <-- clear
 sudo ir-keytable -s rc2 -t
   

리모컨 키값
모든키는 마지막에 code 00, type 00, val 00 코드가 같이 날아옴. 두번 연속 받음.
ch-: code 04, type 04, val 69
ch: code 04, type 04, val 70
ch+: code 04, type 04, val 71

prv: code 04, type 04, val 68
fwd: code 04, type 04, val 64

start/stop: code 04, type 04, val 67
vol down: code 04, type 04, val 07
vol up: code 04, type 04, val 21
eq: code 04, type 04, val 09
0key: code 04, type 04, val 22
100+key: code 04, type 04, val 25
100+key: code 04, type 04, val 13
1key: code 04, type 04, val 12
2key: code 04, type 04, val 24
3key: code 04, type 04, val 94
4key: code 04, type 04, val 08
5key: code 04, type 04, val 28
6key: code 04, type 04, val 90
7key: code 04, type 04, val 66
8key: code 04, type 04, val 82
9key: code 04, type 04, val 74




# install.sh (초안)
sudo apt install -y mplayer cdparanoia i2c-tools
sudo usermod -aG audio,i2c,cdrom pi


#ssh 최초 접속시 에러 발생하면
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

접속하는 윈도우에서: ssh-keygen -R 192.168.219.150
끝

내가 현재 속한 그룹 확인
groups pi
