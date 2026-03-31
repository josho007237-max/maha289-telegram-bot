# MAHA289 Telegram Bot Ready

บอทชุดนี้ทำงานแบบ Long Polling พร้อมใช้สำหรับ:

- เมนูหน้าแรกในแชทส่วนตัว
- เปิดเคสจากลูกค้า
- ส่งเคสเข้า MAHA289 Support Desk
- แอดมินกดรับเคส / คืนให้บอท / ปิดเคส
- แอดมินตอบลูกค้าผ่านการ Reply ในกลุ่ม
- ส่งประกาศไปยัง Channel ด้วยคำสั่ง /publish

## สำคัญมาก
ถ้า token บอทเคยโผล่ในรูปหรือแชท ให้ไปออก token ใหม่กับ `@BotFather` ก่อนใช้งาน

---

## 1) ติดตั้ง

### Windows
1. แตก zip
2. คัดลอก `.env.example` เป็น `.env`
3. ใส่ค่าใน `.env`
4. ดับเบิลคลิก `run.bat`

### Linux / macOS / VPS
```bash
cp .env.example .env
nano .env
chmod +x run.sh
./run.sh
```

---

## 2) ตั้งค่า `.env`

```env
BOT_TOKEN=วาง_token_ใหม่ที่นี่
BOT_USERNAME=MAHA289CareBot_bot
CHANNEL_USERNAME=MAHA289Care
ADMIN_GROUP_ID=
DB_PATH=bot.db
```

- `ADMIN_GROUP_ID` เว้นว่างได้ก่อน
- หลังรันบอทแล้ว ให้ไปที่กลุ่ม `MAHA289 Support Desk` แล้วพิมพ์ `/binddesk`

---

## 3) ตั้ง Telegram ให้ครบ

### A. ใน MAHA289 Support Desk
- เพิ่มบอทเข้า group
- พิมพ์ `/binddesk`

### B. ใน MAHA289 News
- เพิ่มบอทเป็นแอดมิน ถ้าต้องการใช้ `/publish`

---

## 4) วิธีใช้

### ลูกค้า
- `/start`
- กด `ติดต่อแอดมิน`
- เลือกหมวด
- พิมพ์ข้อความ
- ระบบจะสร้างเคส

### แอดมิน
- กดปุ่ม `✅ รับเคส`
- ตอบลูกค้าโดย Reply ใต้ข้อความลูกค้าที่บอทคัดลอกมา
- ปิดงานด้วย `🔒 ปิดเคส`

### ส่งประกาศเข้า Channel
พิมพ์ในกลุ่ม Support Desk:
```text
/publish แจ้งข่าวหรือโปรโมชั่นที่ต้องการโพสต์
```

---

## 5) เช็คเออเร่อเร็ว

### เช็ค token
```bash
curl https://api.telegram.org/bot<BOT_TOKEN>/getMe
```

### ลบ webhook ถ้าเคยตั้งไว้
```bash
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook?drop_pending_updates=true"
```

### ปัญหาพบบ่อย
- บอทไม่เห็นเคส -> ยังไม่ได้ `/binddesk`
- `/publish` ไม่ได้ -> บอทยังไม่เป็นแอดมินใน channel
- แอดมินตอบแล้วลูกค้าไม่ได้รับ -> แอดมินไม่ได้ Reply ใต้ข้อความลูกค้า
- บอทเงียบ -> ใช้ token ผิด หรือมี webhook ค้าง

---

## 6) ไม่ต้องขึ้น GitHub ก็ได้

คุณสามารถรันได้เลยบน:
- คอมตัวเอง
- VPS
- เครื่อง Windows ที่เปิดค้างไว้

GitHub มีประโยชน์เมื่อ:
- อยากสำรองโค้ด
- อยาก deploy อัตโนมัติ
- อยากให้ทีมช่วยแก้โค้ด
