// i18n: all UI strings in Indonesian (id), English (en) and Arabic (ar, RTL).
// Backend errors arrive as codes (e.g. EMAIL_INVALID) and are translated here via `err_<CODE>`.
import React, { createContext, useContext, useEffect, useState } from "react";

const errors = {
  id: {
    err_INVALID_ID: "ID tidak valid", err_NOT_AUTHENTICATED: "Silakan masuk terlebih dahulu",
    err_TOKEN_EXPIRED: "Sesi berakhir, silakan masuk lagi", err_TOKEN_INVALID: "Sesi tidak valid",
    err_TOKEN_REVOKED: "Sesi telah dicabut, silakan masuk lagi", err_USER_NOT_FOUND: "Pengguna tidak ditemukan",
    err_FORBIDDEN: "Anda tidak punya akses", err_AUTH_INVALID_CREDENTIALS: "Email atau kata sandi salah",
    err_ACCOUNT_INACTIVE: "Akun tidak aktif", err_LOGIN_LOCKED: "Terlalu banyak percobaan. Coba lagi dalam 15 menit",
    err_PASSWORD_EMPTY: "Kata sandi tidak boleh kosong", err_PASSWORD_TOO_SHORT: "Kata sandi terlalu pendek",
    err_PASSWORD_CURRENT_WRONG: "Kata sandi saat ini salah", err_PASSWORD_SAME: "Kata sandi baru harus berbeda",
    err_EMAIL_INVALID: "Alamat email tidak valid", err_EMAIL_TAKEN: "Email sudah digunakan",
    err_CANNOT_MANAGE_ROLE: "Anda tidak boleh mengelola peran ini", err_CANNOT_MODIFY_SELF: "Anda tidak bisa mengubah akun sendiri di sini",
    err_LAST_SUPER_ADMIN: "Super admin terakhir tidak bisa dinonaktifkan", err_ITEM_NOT_FOUND: "Item menu tidak ditemukan",
    err_ITEM_UNAVAILABLE: "Item sedang habis", err_OPTION_INVALID: "Pilihan tidak valid", err_OPTION_REQUIRED: "Pilihan wajib belum dipilih",
    err_ORDERS_PAUSED: "Pemesanan sedang dihentikan sementara", err_CART_EMPTY: "Keranjang kosong",
    err_TABLE_INVALID: "Nomor meja tidak valid", err_CUSTOMER_NAME_REQUIRED: "Nama pemesan wajib diisi",
    err_ORDER_NOT_FOUND: "Pesanan tidak ditemukan", err_ORDER_TOKEN_INVALID: "Anda tidak punya akses ke pesanan ini",
    err_ORDER_ALREADY_ACCEPTED: "Pesanan sudah diterima kasir lain", err_ORDER_NOT_OWNER: "Hanya kasir penanggung jawab yang bisa mengubah",
    err_STATUS_INVALID: "Status tidak valid", err_STATUS_NOT_SEQUENTIAL: "Alur status harus berurutan",
    err_ORDER_CLOSED: "Pesanan sudah ditutup dan tidak bisa diubah", err_EDIT_WINDOW_CLOSED: "Jendela edit telah berakhir",
    err_CALL_NOT_FOUND: "Panggilan tidak ditemukan", err_RATING_TOO_EARLY: "Penilaian hanya setelah pesanan diantar",
    err_RATING_EXISTS: "Pesanan ini sudah dinilai", err_NO_ACTIVE_SHIFT: "Tidak ada shift aktif",
    err_RATE_LIMITED: "Terlalu banyak permintaan, coba lagi sebentar", err_UNKNOWN: "Terjadi kesalahan",
  },
  en: {
    err_INVALID_ID: "Invalid id", err_NOT_AUTHENTICATED: "Please sign in first",
    err_TOKEN_EXPIRED: "Session expired, please sign in again", err_TOKEN_INVALID: "Invalid session",
    err_TOKEN_REVOKED: "Session revoked, please sign in again", err_USER_NOT_FOUND: "User not found",
    err_FORBIDDEN: "You don't have access", err_AUTH_INVALID_CREDENTIALS: "Wrong email or password",
    err_ACCOUNT_INACTIVE: "Account is inactive", err_LOGIN_LOCKED: "Too many attempts. Try again in 15 minutes",
    err_PASSWORD_EMPTY: "Password cannot be empty", err_PASSWORD_TOO_SHORT: "Password is too short",
    err_PASSWORD_CURRENT_WRONG: "Current password is wrong", err_PASSWORD_SAME: "New password must be different",
    err_EMAIL_INVALID: "Invalid email address", err_EMAIL_TAKEN: "Email already in use",
    err_CANNOT_MANAGE_ROLE: "You may not manage this role", err_CANNOT_MODIFY_SELF: "You cannot change your own account here",
    err_LAST_SUPER_ADMIN: "The last super admin cannot be disabled", err_ITEM_NOT_FOUND: "Menu item not found",
    err_ITEM_UNAVAILABLE: "Item is sold out", err_OPTION_INVALID: "Invalid option", err_OPTION_REQUIRED: "A required option is missing",
    err_ORDERS_PAUSED: "Ordering is paused right now", err_CART_EMPTY: "Cart is empty",
    err_TABLE_INVALID: "Invalid table number", err_CUSTOMER_NAME_REQUIRED: "Customer name is required",
    err_ORDER_NOT_FOUND: "Order not found", err_ORDER_TOKEN_INVALID: "You don't have access to this order",
    err_ORDER_ALREADY_ACCEPTED: "Order was already accepted by another cashier", err_ORDER_NOT_OWNER: "Only the responsible cashier can change this",
    err_STATUS_INVALID: "Invalid status", err_STATUS_NOT_SEQUENTIAL: "Status must move one step at a time",
    err_ORDER_CLOSED: "Order is closed and cannot be changed", err_EDIT_WINDOW_CLOSED: "Edit window has ended",
    err_CALL_NOT_FOUND: "Call not found", err_RATING_TOO_EARLY: "You can rate after the order is delivered",
    err_RATING_EXISTS: "This order was already rated", err_NO_ACTIVE_SHIFT: "No active shift",
    err_RATE_LIMITED: "Too many requests, please wait a moment", err_UNKNOWN: "Something went wrong",
  },
  ar: {
    err_INVALID_ID: "معرّف غير صالح", err_NOT_AUTHENTICATED: "يرجى تسجيل الدخول أولاً",
    err_TOKEN_EXPIRED: "انتهت الجلسة، سجّل الدخول مجدداً", err_TOKEN_INVALID: "جلسة غير صالحة",
    err_TOKEN_REVOKED: "تم إنهاء الجلسة، سجّل الدخول مجدداً", err_USER_NOT_FOUND: "المستخدم غير موجود",
    err_FORBIDDEN: "ليست لديك صلاحية", err_AUTH_INVALID_CREDENTIALS: "البريد أو كلمة المرور غير صحيحة",
    err_ACCOUNT_INACTIVE: "الحساب غير نشط", err_LOGIN_LOCKED: "محاولات كثيرة. حاول بعد 15 دقيقة",
    err_PASSWORD_EMPTY: "كلمة المرور لا يمكن أن تكون فارغة", err_PASSWORD_TOO_SHORT: "كلمة المرور قصيرة جداً",
    err_PASSWORD_CURRENT_WRONG: "كلمة المرور الحالية غير صحيحة", err_PASSWORD_SAME: "يجب أن تختلف كلمة المرور الجديدة",
    err_EMAIL_INVALID: "البريد الإلكتروني غير صالح", err_EMAIL_TAKEN: "البريد مستخدم مسبقاً",
    err_CANNOT_MANAGE_ROLE: "لا يمكنك إدارة هذا الدور", err_CANNOT_MODIFY_SELF: "لا يمكنك تعديل حسابك من هنا",
    err_LAST_SUPER_ADMIN: "لا يمكن تعطيل آخر سوبر أدمن", err_ITEM_NOT_FOUND: "الصنف غير موجود",
    err_ITEM_UNAVAILABLE: "الصنف نفد", err_OPTION_INVALID: "خيار غير صالح", err_OPTION_REQUIRED: "خيار إلزامي لم يُحدَّد",
    err_ORDERS_PAUSED: "الطلبات متوقفة مؤقتاً", err_CART_EMPTY: "السلة فارغة",
    err_TABLE_INVALID: "رقم الطاولة غير صالح", err_CUSTOMER_NAME_REQUIRED: "اسم العميل مطلوب",
    err_ORDER_NOT_FOUND: "الطلب غير موجود", err_ORDER_TOKEN_INVALID: "ليست لديك صلاحية لهذا الطلب",
    err_ORDER_ALREADY_ACCEPTED: "قبل كاشير آخر هذا الطلب", err_ORDER_NOT_OWNER: "فقط الكاشير المسؤول يمكنه التعديل",
    err_STATUS_INVALID: "حالة غير صالحة", err_STATUS_NOT_SEQUENTIAL: "يجب تغيير الحالة خطوة بخطوة",
    err_ORDER_CLOSED: "الطلب مغلق ولا يمكن تعديله", err_EDIT_WINDOW_CLOSED: "انتهت مهلة التعديل",
    err_CALL_NOT_FOUND: "النداء غير موجود", err_RATING_TOO_EARLY: "يمكن التقييم بعد تقديم الطلب",
    err_RATING_EXISTS: "تم تقييم هذا الطلب مسبقاً", err_NO_ACTIVE_SHIFT: "لا توجد وردية نشطة",
    err_RATE_LIMITED: "طلبات كثيرة، انتظر قليلاً", err_UNKNOWN: "حدث خطأ",
  },
};

const dict = {
  id: {
    ...errors.id,
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
    printInvoice: "Cetak Struk", viewInvoice: "Lihat Struk", paidStamp: "LUNAS", thanksVisit: "Terima kasih atas kunjungan Anda",
    soldOut: "Habis", soldOutPanel: "Ketersediaan Menu", newOrderAlert: "Pesanan baru masuk!", soundOn: "Suara aktif", soundOff: "Suara mati",
    status_new: "Baru", status_accepted: "Diterima", status_preparing: "Disiapkan",
    status_ready: "Siap", status_delivered: "Diantar", status_closed: "Selesai",
    resolve: "Selesaikan", noOrders: "Belum ada pesanan", scanTitle: "Pesan dari meja Anda",
    ordersCount: "Jumlah Pesanan", totalCash: "Total Uang", role: "Peran",
    active: "Aktif", inactive: "Nonaktif", addStaff: "Tambah Karyawan",
    handledBy: "Ditangani oleh", placedAt: "Dipesan", options: "Pilihan",
    orderPlaced: "Pesanan Terkirim!", orderPlacedDesc: "Dapur kami sudah menerima pesanan Anda.",
    orderNumber: "Nomor Pesanan", trackOrder: "Lihat Status Pesanan", close: "Tutup",
    // Phase 1 additions
    role_super_admin: "Super Admin", role_owner: "Pemilik", role_cashier: "Kasir",
    changePassword: "Ganti Kata Sandi", currentPassword: "Kata sandi saat ini", newPassword: "Kata sandi baru",
    confirmPassword: "Ulangi kata sandi baru", passwordMismatch: "Kata sandi tidak sama", passwordChanged: "Kata sandi berhasil diganti",
    resetPassword: "Reset Kata Sandi", deactivate: "Nonaktifkan", reactivate: "Aktifkan", deleteStaff: "Hapus Karyawan",
    deleteStaffConfirm: "Hapus karyawan ini? Jika punya riwayat pesanan, akun akan dianonimkan dan dinonaktifkan.",
    deactivateConfirm: "Nonaktifkan akun ini? Mereka tidak bisa masuk lagi.", you: "Anda",
    staffDeleted: "Karyawan dihapus", staffAnonymized: "Karyawan dianonimkan & dinonaktifkan",
    editWindowNote: "Jendela edit {n} detik setelah diterima.", adminPanel: "Super Admin",
    customerName: "Nama pemesan", customerNamePh: "Nama Anda", ordersPaused: "Pemesanan sedang dihentikan sementara. Silakan hubungi kasir.",
    yes: "Ya", no: "Tidak", enabled: "Aktif", disabled: "Nonaktif",
    // Settings sections
    sec_general: "Umum", sec_time: "Waktu & Bahasa", sec_money: "Uang", sec_orders: "Pesanan", sec_inventory: "Stok", sec_security: "Keamanan",
    s_restaurant_name: "Nama restoran", s_logo: "URL logo", s_primary_color: "Warna utama", s_phone: "Telepon", s_address: "Alamat",
    s_opening_hours: "Jam buka", s_receipt_footer: "Teks kaki struk", s_wifi_name: "Nama Wi-Fi", s_wifi_password: "Kata sandi Wi-Fi",
    s_timezone: "Zona waktu", s_business_day_start: "Awal hari kerja", s_business_day_end: "Akhir hari kerja",
    s_language: "Bahasa default", s_enabled_languages: "Bahasa untuk pelanggan",
    s_currency: "Mata uang", s_tax_rate: "Pajak %", s_tax_enabled: "Pajak aktif", s_service_charge: "Biaya layanan %", s_service_enabled: "Biaya layanan aktif",
    s_prices_include_tax: "Harga sudah termasuk pajak", s_payment_methods: "Metode pembayaran", s_rounding: "Pembulatan",
    pm_cash: "Tunai", pm_card: "Kartu", pm_qris: "QRIS", pm_other: "Lainnya", round_none: "Tidak ada", round_100: "Ke 100 terdekat", round_500: "Ke 500 terdekat",
    s_table_count: "Jumlah meja", s_edit_window_seconds: "Jendela edit (detik)", s_require_customer_name: "Nama pemesan wajib",
    s_require_table_number: "Nomor meja wajib", s_accepting_orders: "Menerima pesanan baru", s_new_order_sound: "Suara pesanan baru",
    s_default_low_stock_threshold: "Batas stok rendah default", s_auto_hide_out_of_stock: "Sembunyikan menu saat stok habis", s_alert_in_app: "Notifikasi di aplikasi",
    s_session_hours: "Lama sesi (jam)", s_min_password_length: "Panjang minimum kata sandi",
    // Admin section
    a_license_expires_at: "Lisensi berakhir (YYYY-MM-DD)", a_billing_enabled: "Penagihan aktif", a_billing_mode: "Mode penagihan",
    a_fee_per_invoice: "Biaya per invoice", a_low_balance_warning: "Peringatan saldo rendah", a_zero_balance_behavior: "Saat saldo habis",
    a_grace_invoices: "Toleransi (jumlah invoice)", a_reversal_refunds_fee: "Pembatalan mengembalikan biaya", a_seed_demo: "Data demo",
    mode_monthly: "Bulanan", mode_prepaid: "Prabayar", zb_warn: "Peringatkan saja", zb_warn_grace: "Peringatkan + toleransi", zb_block: "Blokir langsung",
    adminNote: "Bagian ini hanya terlihat oleh Super Admin. Penagihan mulai berlaku di fase berikutnya.",
  },
  en: {
    ...errors.en,
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
    printInvoice: "Print Receipt", viewInvoice: "View Receipt", paidStamp: "PAID", thanksVisit: "Thank you for your visit",
    soldOut: "Sold out", soldOutPanel: "Menu Availability", newOrderAlert: "New order received!", soundOn: "Sound on", soundOff: "Sound off",
    status_new: "New", status_accepted: "Accepted", status_preparing: "Preparing",
    status_ready: "Ready", status_delivered: "Delivered", status_closed: "Closed",
    resolve: "Resolve", noOrders: "No orders yet", scanTitle: "Order from your table",
    ordersCount: "Orders", totalCash: "Total Cash", role: "Role",
    active: "Active", inactive: "Inactive", addStaff: "Add Staff",
    handledBy: "Handled by", placedAt: "Placed", options: "Options",
    orderPlaced: "Order Sent!", orderPlacedDesc: "Our kitchen has received your order.",
    orderNumber: "Order Number", trackOrder: "Track Order Status", close: "Close",
    role_super_admin: "Super Admin", role_owner: "Owner", role_cashier: "Cashier",
    changePassword: "Change Password", currentPassword: "Current password", newPassword: "New password",
    confirmPassword: "Repeat new password", passwordMismatch: "Passwords do not match", passwordChanged: "Password changed",
    resetPassword: "Reset Password", deactivate: "Deactivate", reactivate: "Reactivate", deleteStaff: "Delete Staff",
    deleteStaffConfirm: "Delete this staff member? If they have order history the account is anonymized and deactivated instead.",
    deactivateConfirm: "Deactivate this account? They will no longer be able to sign in.", you: "You",
    staffDeleted: "Staff deleted", staffAnonymized: "Staff anonymized & deactivated",
    editWindowNote: "Edit window: {n} seconds after acceptance.", adminPanel: "Super Admin",
    customerName: "Customer name", customerNamePh: "Your name", ordersPaused: "Ordering is paused right now. Please ask the cashier.",
    yes: "Yes", no: "No", enabled: "Enabled", disabled: "Disabled",
    sec_general: "General", sec_time: "Time & Language", sec_money: "Money", sec_orders: "Orders", sec_inventory: "Inventory", sec_security: "Security",
    s_restaurant_name: "Restaurant name", s_logo: "Logo URL", s_primary_color: "Primary color", s_phone: "Phone", s_address: "Address",
    s_opening_hours: "Opening hours", s_receipt_footer: "Receipt footer text", s_wifi_name: "Wi-Fi name", s_wifi_password: "Wi-Fi password",
    s_timezone: "Timezone", s_business_day_start: "Business day start", s_business_day_end: "Business day end",
    s_language: "Default language", s_enabled_languages: "Customer languages",
    s_currency: "Currency", s_tax_rate: "Tax %", s_tax_enabled: "Tax enabled", s_service_charge: "Service charge %", s_service_enabled: "Service charge enabled",
    s_prices_include_tax: "Prices include tax", s_payment_methods: "Payment methods", s_rounding: "Rounding",
    pm_cash: "Cash", pm_card: "Card", pm_qris: "QRIS", pm_other: "Other", round_none: "None", round_100: "Nearest 100", round_500: "Nearest 500",
    s_table_count: "Number of tables", s_edit_window_seconds: "Edit window (seconds)", s_require_customer_name: "Customer name required",
    s_require_table_number: "Table number required", s_accepting_orders: "Accepting new orders", s_new_order_sound: "New-order sound",
    s_default_low_stock_threshold: "Default low-stock threshold", s_auto_hide_out_of_stock: "Hide menu items when out of stock", s_alert_in_app: "In-app alerts",
    s_session_hours: "Session length (hours)", s_min_password_length: "Minimum password length",
    a_license_expires_at: "License expires (YYYY-MM-DD)", a_billing_enabled: "Billing enabled", a_billing_mode: "Billing mode",
    a_fee_per_invoice: "Fee per invoice", a_low_balance_warning: "Low balance warning", a_zero_balance_behavior: "When balance hits zero",
    a_grace_invoices: "Grace (invoices)", a_reversal_refunds_fee: "Reversal refunds the fee", a_seed_demo: "Demo data",
    mode_monthly: "Monthly", mode_prepaid: "Prepaid", zb_warn: "Warn only", zb_warn_grace: "Warn + grace", zb_block: "Block immediately",
    adminNote: "Only the Super Admin sees this section. Billing takes effect in a later phase.",
  },
  ar: {
    ...errors.ar,
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
    printInvoice: "طباعة الفاتورة", viewInvoice: "عرض الفاتورة", paidStamp: "مدفوع", thanksVisit: "شكراً لزيارتكم",
    soldOut: "نفد", soldOutPanel: "توفر الأصناف", newOrderAlert: "وصل طلب جديد!", soundOn: "الصوت مفعّل", soundOff: "الصوت مكتوم",
    status_new: "جديد", status_accepted: "مقبول", status_preparing: "قيد التحضير",
    status_ready: "جاهز", status_delivered: "تم التقديم", status_closed: "مغلق",
    resolve: "إنهاء", noOrders: "لا طلبات بعد", scanTitle: "اطلب من طاولتك",
    ordersCount: "عدد الطلبات", totalCash: "إجمالي النقد", role: "الدور",
    active: "نشط", inactive: "غير نشط", addStaff: "إضافة موظف",
    handledBy: "تم التعامل بواسطة", placedAt: "وقت الطلب", options: "الخيارات",
    orderPlaced: "تم إرسال الطلب!", orderPlacedDesc: "استلم المطبخ طلبك بنجاح.",
    orderNumber: "رقم الطلب", trackOrder: "تتبع حالة الطلب", close: "إغلاق",
    role_super_admin: "سوبر أدمن", role_owner: "المالك", role_cashier: "كاشير",
    changePassword: "تغيير كلمة المرور", currentPassword: "كلمة المرور الحالية", newPassword: "كلمة المرور الجديدة",
    confirmPassword: "أعد كتابة كلمة المرور", passwordMismatch: "كلمتا المرور غير متطابقتين", passwordChanged: "تم تغيير كلمة المرور",
    resetPassword: "إعادة تعيين كلمة المرور", deactivate: "تعطيل", reactivate: "تفعيل", deleteStaff: "حذف الموظف",
    deleteStaffConfirm: "حذف هذا الموظف؟ إذا كان له سجل طلبات فسيُخفى اسمه ويُعطَّل الحساب بدلاً من الحذف.",
    deactivateConfirm: "تعطيل هذا الحساب؟ لن يتمكن من تسجيل الدخول.", you: "أنت",
    staffDeleted: "تم حذف الموظف", staffAnonymized: "تم إخفاء هوية الموظف وتعطيله",
    editWindowNote: "مهلة التعديل {n} ثانية بعد القبول.", adminPanel: "سوبر أدمن",
    customerName: "اسم العميل", customerNamePh: "اسمك", ordersPaused: "الطلبات متوقفة مؤقتاً. يرجى مراجعة الكاشير.",
    yes: "نعم", no: "لا", enabled: "مفعّل", disabled: "معطّل",
    sec_general: "عام", sec_time: "الوقت واللغة", sec_money: "المال", sec_orders: "الطلبات", sec_inventory: "المخزون", sec_security: "الأمان",
    s_restaurant_name: "اسم المطعم", s_logo: "رابط الشعار", s_primary_color: "اللون الرئيسي", s_phone: "الهاتف", s_address: "العنوان",
    s_opening_hours: "ساعات العمل", s_receipt_footer: "نص أسفل الفاتورة", s_wifi_name: "اسم الواي فاي", s_wifi_password: "كلمة مرور الواي فاي",
    s_timezone: "المنطقة الزمنية", s_business_day_start: "بداية يوم العمل", s_business_day_end: "نهاية يوم العمل",
    s_language: "اللغة الافتراضية", s_enabled_languages: "لغات العملاء",
    s_currency: "العملة", s_tax_rate: "الضريبة %", s_tax_enabled: "الضريبة مفعّلة", s_service_charge: "رسوم الخدمة %", s_service_enabled: "رسوم الخدمة مفعّلة",
    s_prices_include_tax: "الأسعار شاملة الضريبة", s_payment_methods: "طرق الدفع", s_rounding: "التقريب",
    pm_cash: "نقداً", pm_card: "بطاقة", pm_qris: "QRIS", pm_other: "أخرى", round_none: "بدون", round_100: "لأقرب 100", round_500: "لأقرب 500",
    s_table_count: "عدد الطاولات", s_edit_window_seconds: "مهلة التعديل (ثانية)", s_require_customer_name: "اسم العميل إلزامي",
    s_require_table_number: "رقم الطاولة إلزامي", s_accepting_orders: "استقبال طلبات جديدة", s_new_order_sound: "صوت الطلب الجديد",
    s_default_low_stock_threshold: "حد المخزون المنخفض الافتراضي", s_auto_hide_out_of_stock: "إخفاء الصنف عند نفاد المخزون", s_alert_in_app: "تنبيهات داخل التطبيق",
    s_session_hours: "مدة الجلسة (ساعات)", s_min_password_length: "الحد الأدنى لطول كلمة المرور",
    a_license_expires_at: "انتهاء الترخيص (YYYY-MM-DD)", a_billing_enabled: "الفوترة مفعّلة", a_billing_mode: "نمط الفوترة",
    a_fee_per_invoice: "الرسوم لكل فاتورة", a_low_balance_warning: "تنبيه الرصيد المنخفض", a_zero_balance_behavior: "عند نفاد الرصيد",
    a_grace_invoices: "سماحية (عدد الفواتير)", a_reversal_refunds_fee: "الإلغاء يعيد الرسوم", a_seed_demo: "بيانات تجريبية",
    mode_monthly: "شهري", mode_prepaid: "مسبق الدفع", zb_warn: "تنبيه فقط", zb_warn_grace: "تنبيه + سماحية", zb_block: "حظر فوري",
    adminNote: "هذا القسم يراه السوبر أدمن فقط. الفوترة تبدأ في مرحلة لاحقة.",
  },
};

const I18nCtx = createContext(null);

// Reads the current language outside React (used by errMsg in api.js).
export const currentLang = () => localStorage.getItem("restos_lang") || "id";

// Translate a backend error code into the active language.
export function errText(code, extra = {}) {
  const l = currentLang();
  const s = dict[l]?.[`err_${code}`] ?? dict.en[`err_${code}`] ?? dict[l]?.err_UNKNOWN ?? dict.en.err_UNKNOWN;
  return extra.min_length ? `${s} (${extra.min_length})` : s;
}

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(currentLang);
  useEffect(() => {
    localStorage.setItem("restos_lang", lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);
  // t(key, vars) replaces {name} placeholders.
  const t = (k, vars) => {
    let s = dict[lang]?.[k] ?? dict.en[k] ?? k;
    if (vars) Object.entries(vars).forEach(([key, v]) => { s = s.replace(`{${key}}`, v); });
    return s;
  };
  return <I18nCtx.Provider value={{ lang, setLang, t, rtl: lang === "ar" }}>{children}</I18nCtx.Provider>;
}

export const useI18n = () => useContext(I18nCtx);

// Pick the translated field of a content object (menu item, category, option) with fallback.
export function localized(obj, field, lang) {
  if (!obj) return "";
  if (lang === "en") return obj[`${field}_en`] || obj[field] || "";
  if (lang === "ar") return obj[`${field}_ar`] || obj[field] || "";
  return obj[field] || "";
}

export const LANGS = [
  { code: "id", label: "ID" },
  { code: "en", label: "EN" },
  { code: "ar", label: "AR" },
];
