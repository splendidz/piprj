# 라즈베리파이 부팅 시 CD 플레이어 자동 실행

**Raspberry Pi OS는 데스크톱으로 LXDE를 쓰며, `~/.config/autostart/` 가 아니라 lxsession 의 autostart 파일을 사용합니다.**

---

## 방법: lxsession autostart (데스크톱 뜬 뒤 실행)

### 1) 실행 스크립트 한 번 설정

```bash
chmod +x /home/pi/codes/piprj/run_cdplayer.sh
```

conda 경로가 다르면 `run_cdplayer.sh` 안의 `PYTHON=` 줄을 수정하세요.  
(터미널에서 `conda activate gym` 후 `which python` 으로 경로 확인)

### 2) 사용자 autostart 파일 만들기

**사용자 전용** (pi 로그인 시에만 실행):

```bash
mkdir -p ~/.config/lxsession/LXDE-pi
nano ~/.config/lxsession/LXDE-pi/autostart
```

아래 내용을 **통째로** 넣고 저장합니다. (기존 항목이 있으면 그 아래에 한 줄만 추가해도 됨.)

```
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@/home/pi/codes/piprj/run_cdplayer.sh
```

- `@` 는 선택사항입니다.
- **한 줄만 추가**하려면: 마지막에 `@/home/pi/codes/piprj/run_cdplayer.sh` 만 넣으면 됩니다.  
  (이 경우 데스크톱 기본 항목은 이미 시스템 파일에서 오므로, 사용자 파일이 시스템 파일을 **완전히 대체**한다는 점만 주의.)

### 3) 시스템 전체에 적용 (모든 사용자)

```bash
sudo nano /etc/xdg/lxsession/LXDE-pi/autostart
```

맨 아래에 한 줄 추가:

```
@/home/pi/codes/piprj/run_cdplayer.sh
```

저장 후 재부팅해서 데스크톱이 뜬 뒤 CD 플레이어가 자동 실행되는지 확인하세요.

### 4) 안 되면 로그 확인

실행/에러는 다음 파일에 남습니다.

```bash
cat /home/pi/codes/piprj/autostart.log
```

---

## 요약

| 환경 | 사용하는 위치 |
|------|----------------|
| Raspberry Pi OS 데스크톱 (LXDE) | **~/.config/lxsession/LXDE-pi/autostart** 또는 **/etc/xdg/lxsession/LXDE-pi/autostart** (한 줄 추가) |
| `~/.config/autostart/*.desktop` | LXDE 기본 설정에서는 **읽지 않음** (동작 안 함) |

추가한 **한 줄**이 곧 등록입니다. 별도 등록 절차 없습니다.
