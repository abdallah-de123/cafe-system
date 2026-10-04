import React, { createContext, useContext, useEffect, useState } from "react";

const dict = {
  id: {
    menu: "Menu", cart: "Keranjang", search: "Cari menu...", all: "Semua",
    addToCart: "Tambah ke Keranjang", qty: "Jumlah", note: "Catatan",
    notePh: "cth: jangan pakai bawang", submitOrder: "Kirim Pesanan",
    table: "Meja", subtotal: "Subtotal", tax: "Pajak (PPN)", service: "Biaya Layanan",
    total: "Total", orderStatus: "Status Pesanan", invoice: "Invoice",
    callWaiter: "Panggil Kasir", needHelp: "Butuh Bantuan", requestBill: "Minta Bill",
    cleanTable: "Bersihkan Meja", rateOrder: "Beri Penilaian", food: "Makanan",
    serviceR: "Pelayanan", speed: "Kecepatan", sendRating: "Kirim Penilaian",
    thanks: "Terima kasih atas penilaian Anda!", emptyCart: "Keranjang masih kosong",
    myOrders: "Pesanan Saya", login: "Masuk", logout: "Keluar", email: "Email",
    password: "Kata Sandi", dashboard: "Dasbor", orders: "Pesanan", staff: "Karyawan",
    reports: "Laporan", settings: "Pengaturan", auditLog: "Log Audit", calls: "Panggilan",
    shift: "Shift", accept: "Terima", startShift: "Mulai Shift", endShift: "Akhiri Shift",
    revenue: "Pendapatan", avgOrder: "Rata-rata Pesanan", bestSellers: "Terlaris",
    worstSellers: "Kurang Diminati", busiestHours: "Jam Tersibuk", addItem: "Tambah Item",
    save: "Simpan", cancel: "Batal", delete: "Hapus", edit: "Ubah", price: "Harga",
    category: "Kategori", available: "Tersedia", name: "Nama", desc: "Deskripsi",
    tables: "Meja & QR", markPaid: "Tandai Lunas & Tutup", newOrders: "Pesanan Baru",
    status_new: "Baru", status_accepted: "Diterima", status_preparing: "Disiapkan",
    status_ready: "Siap", status_delivered: "Diantar", status_closed: "Selesai",
    resolve: "Selesaikan", noOrders: "Belum ada pesanan", scanTitle: "Pesan dari meja Anda",
    ordersCount: "Jumlah Pesanan", totalCash: "Total Uang", role: "Peran",
    active: "Aktif", inactive: "Nonaktif", addStaff: "Tambah Karyawan",
    handledBy: "Ditangani oleh", placedAt: "Dipesan", options: "Pilihan",
  },
  en: {
    menu: "Menu", cart: "Cart", search: "Search menu...", all: "All",
    addToCart: "Add to Cart", qty: "Quantity", note: "Note",
    notePh: "e.g. no onions please", submitOrder: "Submit Order",
    table: "Table", subtotal: "Subtotal", tax: "Tax (VAT)", service: "Service Charge",
    total: "Total", orderStatus: "Order Status", invoice: "Invoice",
    callWaiter: "Call Cashier", needHelp: "Need Help", requestBill: "Request Bill",
    cleanTable: "Clean Table", rateOrder: "Rate Your Order", food: "Food",
    serviceR: "Service", speed: "Speed", sendRating: "Send Rating",
    thanks: "Thanks for your feedback!", emptyCart: "Your cart is empty",
    myOrders: "My Orders", login: "Sign In", logout: "Sign Out", email: "Email",
    password: "Password", dashboard: "Dashboard", orders: "Orders", staff: "Staff",
    reports: "Reports", settings: "Settings", auditLog: "Audit Log", calls: "Calls",
    shift: "Shift", accept: "Accept", startShift: "Start Shift", endShift: "End Shift",
    revenue: "Revenue", avgOrder: "Avg Order Value", bestSellers: "Best Sellers",
    worstSellers: "Worst Sellers", busiestHours: "Busiest Hours", addItem: "Add Item",
    save: "Save", cancel: "Cancel", delete: "Delete", edit: "Edit", price: "Price",
    category: "Category", available: "Available", name: "Name", desc: "Description",
    tables: "Tables & QR", markPaid: "Mark Paid & Close", newOrders: "New Orders",
    status_new: "New", status_accepted: "Accepted", status_preparing: "Preparing",
    status_ready: "Ready", status_delivered: "Delivered", status_closed: "Closed",
    resolve: "Resolve", noOrders: "No orders yet", scanTitle: "Order from your table",
    ordersCount: "Orders", totalCash: "Total Cash", role: "Role",
    active: "Active", inactive: "Inactive", addStaff: "Add Staff",
    handledBy: "Handled by", placedAt: "Placed", options: "Options",
  },
  ar: {
    menu: "القائمة", cart: "السلة", search: "ابحث في القائمة...", all: "الكل",
    addToCart: "أضف إلى السلة", qty: "الكمية", note: "ملاحظة",
    notePh: "مثال: بدون بصل", submitOrder: "إرسال الطلب",
    table: "طاولة", subtotal: "المجموع الفرعي", tax: "الضريبة", service: "رسوم الخدمة",
    total: "الإجمالي", orderStatus: "حالة الطلب", invoice: "الفاتورة",
    callWaiter: "نداء الكاشير", needHelp: "أحتاج مساعدة", requestBill: "طلب الفاتورة",
    cleanTable: "تنظيف الطاولة", rateOrder: "قيّم طلبك", food: "الطعام",
    serviceR: "الخدمة", speed: "السرعة", sendRating: "إرسال التقييم",
    thanks: "شكراً على تقييمك!", emptyCart: "سلتك فارغة",
    myOrders: "طلباتي", login: "تسجيل الدخول", logout: "تسجيل الخروج", email: "البريد",
    password: "كلمة المرور", dashboard: "لوحة التحكم", orders: "الطلبات", staff: "الموظفون",
    reports: "التقارير", settings: "الإعدادات", auditLog: "سجل التدقيق", calls: "النداءات",
    shift: "الوردية", accept: "قبول", startShift: "بدء الوردية", endShift: "إنهاء الوردية",
    revenue: "الإيرادات", avgOrder: "متوسط الطلب", bestSellers: "الأكثر مبيعاً",
    worstSellers: "الأقل مبيعاً", busiestHours: "أكثر الساعات ازدحاماً", addItem: "إضافة عنصر",
    save: "حفظ", cancel: "إلغاء", delete: "حذف", edit: "تعديل", price: "السعر",
    category: "الفئة", available: "متوفر", name: "الاسم", desc: "الوصف",
    tables: "الطاولات ورمز QR", markPaid: "تأكيد الدفع وإغلاق", newOrders: "طلبات جديدة",
    status_new: "جديد", status_accepted: "مقبول", status_preparing: "قيد التحضير",
    status_ready: "جاهز", status_delivered: "تم التقديم", status_closed: "مغلق",
    resolve: "إنهاء", noOrders: "لا طلبات بعد", scanTitle: "اطلب من طاولتك",
    ordersCount: "عدد الطلبات", totalCash: "إجمالي النقد", role: "الدور",
    active: "نشط", inactive: "غير نشط", addStaff: "إضافة موظف",
    handledBy: "تم التعامل بواسطة", placedAt: "وقت الطلب", options: "الخيارات",
  },
};

const I18nCtx = createContext(null);

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem("restos_lang") || "id");
  useEffect(() => {
    localStorage.setItem("restos_lang", lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);
  const t = (k) => dict[lang]?.[k] ?? dict.en[k] ?? k;
  return <I18nCtx.Provider value={{ lang, setLang, t, rtl: lang === "ar" }}>{children}</I18nCtx.Provider>;
}

export const useI18n = () => useContext(I18nCtx);
export const LANGS = [
  { code: "id", label: "ID" },
  { code: "en", label: "EN" },
  { code: "ar", label: "AR" },
];
