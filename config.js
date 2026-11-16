// إعدادات موقع Fottballcia
window.FB_CONFIG = {
  siteName: "Fottballcia",

  // اتركه فارغًا لاستخدام data/live.json (يتحدث كل ~10 دقايق عبر GitHub Actions).
  // للتحديث اللحظي (كل 15-30 ثانية) ضع رابط HTTPS لسيرفرك الذي يشغّل: python3 sports_bot.py loop
  // مثال: "https://live.yourdomain.com/"
  liveEndpoint: "",

  // كل كم مللي ثانية تعيد الصفحات المباشرة تحميل البيانات
  refreshMs: 15000,

  // المنطقة الزمنية لعرض مواعيد المباريات
  timeZone: "Asia/Riyadh"
};
