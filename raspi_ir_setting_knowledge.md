
---

# 📘 Raspberry Pi IR Receiver & systemd Setup Guide

> 목적
> 부팅 직후 IR 리모컨이 동작하지 않는 문제를 방지하고
> 장치 경로 변경 / event 번호 변경 / 초기화 타이밍 문제를
> 재발하지 않도록 정리한 초기 세팅 문서.

---

# 1️⃣ 증상 정리

부팅 직후 IR 리모컨이 동작하지 않음.

수동으로 아래 명령 실행하면 정상 동작:

```bash
ir-keytable <= 이걸로 rc 몇인지 확인
sudo ir-keytable -s rc0 -p all
ir-keytable -c
sudo ir-keytable -s rc0 -t
```

---

# 2️⃣ 원인 분석

## A. 부팅 타이밍 문제

* rc 디바이스 생성 전 초기화 실행
* overlay는 등록되었지만 입력 장치 준비가 늦음

## B. 프로토콜/키맵 초기화 안 된 상태

* 기본 상태에서 프로토콜이 활성화되지 않음
* ir-keytable 실행 시 정상화됨

---

# 3️⃣ 하드웨어 Overlay 설정

파일:

```bash
/boot/config.txt
```

필수 항목:

```ini
[all]
enable_uart=1
dtoverlay=gpio-ir,gpio_pin=18
```

확인:

```bash
lsmod | grep ir
dmesg | grep gpio-ir
```

---

# 4️⃣ rc 디바이스 확인

```bash
ir-keytable
ls -l /sys/class/rc/
```

주의:

* rc0은 고정이 아니다.
* USB IR, HDMI-CEC 등 추가되면 rc1, rc2로 바뀔 수 있음.

---

# 5️⃣ 안정적인 이벤트 경로 사용 (중요)

❌ 잘못된 방식:

```python
IRInputEvdev("/dev/input/event0")
```

event 번호는 바뀔 수 있음.

---

## ✅ 올바른 방식 (by-path 사용)

확인:

```bash
ls -l /dev/input/by-path/
```

예시:

```
platform-ir-receiver@12-event -> ../event0
```

코드:

```python
ir = IRInputEvdev(
    "/dev/input/by-path/platform-ir-receiver@12-event"
)
```

이 경로는 event 번호가 바뀌어도 자동으로 따라감.

---

# 6️⃣ 부팅 시 자동 초기화 (systemd 방식)

## 6.1 초기화 스크립트 생성

```bash
sudo nano /usr/local/bin/ir_init.sh
```

내용:

```bash
#!/bin/bash
set -e

# rc 디바이스 생성 대기
for i in {1..50}; do
  if ls /sys/class/rc/rc* >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

RC="rc0"

/usr/bin/ir-keytable -s "$RC" -p all || true
/usr/bin/ir-keytable -s "$RC" -c || true
```

권한 부여:

```bash
sudo chmod +x /usr/local/bin/ir_init.sh
```

---

## 6.2 systemd 서비스 생성

```bash
sudo nano /etc/systemd/system/ir-init.service
```

내용:

```ini
[Unit]
Description=Initialize IR keytable after boot
After=multi-user.target systemd-udev-settle.service
Wants=systemd-udev-settle.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ir_init.sh

[Install]
WantedBy=multi-user.target
```

---

## 6.3 적용

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ir-init.service
```

확인:

```bash
systemctl status ir-init.service
```

---

# 7️⃣ systemd 개념 정리

| 단계            | 의미            |
| ------------- | ------------- |
| service 파일 생성 | 등록만 됨         |
| daemon-reload | systemd 재읽기   |
| enable        | 부팅 시 자동 실행 등록 |
| start         | 즉시 실행         |

---

# 8️⃣ 등록된 서비스 확인

전체 서비스 파일:

```bash
systemctl list-unit-files --type=service
```

실행 중 서비스:

```bash
systemctl list-units --type=service
```

자동 실행 등록된 서비스:

```bash
systemctl list-unit-files --state=enabled
```

---

# 9️⃣ 디버깅 체크리스트

부팅 직후 문제 발생 시:

```bash
ir-keytable
ls -l /dev/input/by-path/
ls -l /sys/class/rc/
dmesg | grep -i ir
```

---

# 🔟 Python에서 장치 존재 대기 (옵션)

```python
import time
from pathlib import Path

IR_PATH = Path(
    "/dev/input/by-path/platform-ir-receiver@12-event"
)

for _ in range(50):
    if IR_PATH.exists():
        break
    time.sleep(0.1)

ir = IRInputEvdev(str(IR_PATH))
```

---

# 11️⃣ 아키텍처 원칙

1. event 번호 하드코딩 금지
2. rc 번호 고정 가정 금지
3. 초기화는 Python이 아니라 systemd에서 처리
4. 장치 경로는 by-path 사용
5. 부팅 타이밍 고려

---

# 12️⃣ 향후 확장 시 주의

* USB IR 추가 시 rc 번호 변경 가능
* Bluetooth 입력 장치 추가 시 event 순서 변경 가능
* HDMI-CEC 활성화 시 rc 장치 증가 가능

---


IR 안정화의 핵심은:

* overlay 등록
* by-path 사용
* systemd 초기화
* 타이밍 고려

이 네 가지다.

---