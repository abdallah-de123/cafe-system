# REST-OS — Product Requirements Document

## Original problem statement
Build a Restaurant Operating System (REST-OS): a single web app with QR-code table ordering as the core.
Three roles in one app — Customer (no login, via QR at a specific table), Cashier (login, tablet-optimized
dashboard), Owner (login, full management). Strict order lifecycle New → Accepted → Preparing → Ready →
Delivered → Closed, enforced server-side, with real-time updates on both customer and cashier screens.
Invoicing with configurable VAT and service charge, accountability (who accepted/modified, timestamps),
multi-language (Arabic RTL, English, Indonesian), custom branding per restaurant, mobile-first customer menu.

User choices: full end-to-end core in v1, WebSockets for realtime, JWT email+password auth with seeded demo
accounts, demo seed data (5 tables, 15 menu items, 1 owner + 2 cashiers), Indonesian default + IDR currency.

Follow-up request (AR): complete the customer QR interface — category browsing, item detail with options
(size, sugar level, add-ons), cart, order submit with a simple confirmation, 3-language switcher at the top,
full RTL for Arabic.

## Architecture
- Backend: FastAPI (`/app/backend/server.py`), all routes under `/api`, MongoDB via motor, WebSocket at `/api/ws`
  broadcasting `order_created`, `order_updated`, `call_created`, `call_updated`, `menu_updated`, `settings_updated`.
- Auth: JWT (HS256, Bearer token in `localStorage.restos_token`), bcrypt hashes, idempotent startup seeding.
- Frontend: React 19 + Tailwind + shadcn primitives. Routes: `/` landing, `/login`, `/t/:tableNumber` (customer),
  `/cashier`, `/owner`. Contexts: Auth, Settings (branding/currency/tax), I18n (id/en/ar with RTL + content localization).
- Collections: users, menu_items, orders, calls, shifts, ratings, settings, audit_logs, counters.

## User personas
- Customer: scans the table QR, orders from their phone, tracks status live, requests help/bill, rates the meal.
- Cashier: works a tablet during service; accepts orders (ownership lock), moves them through kitchen stages, handles table calls, runs shifts.
- Owner: manages menu, options, staff, tables/QR, branding, tax/service rates; reads reports and the audit log.

## Core requirements (static)
1. QR-based, login-free customer ordering tied to a table number.
2. Strict, server-enforced order lifecycle and unique order number = invoice number.
3. Order ownership: after acceptance only that cashier or the owner may modify; 60s item-edit window.
4. Real-time propagation to customer and staff screens.
5. Invoices with item/add-on breakdown, subtotal, VAT, service charge, total.
6. Accountability: accepted_by, modified_by, per-status timestamps; owner-visible audit log.
7. Trilingual UI + content (ID/EN/AR) with correct RTL.
8. Per-restaurant branding (name, logo, primary color) and configurable currency/tax/service/table count.

## Implemented (2026-06)
- Customer: category pills, search, item sheet with required/optional option groups and price deltas, qty, item note,
  cart with per-line edits, order submit + confirmation dialog (order number + total), live status tracker, full bill
  breakdown, quick calls (help/bill/clean), 1–5 star rating of food/service/speed after delivery.
- Trilingual UI plus translated menu item names, descriptions, category names and option labels; `dir=rtl` for Arabic.
- Cashier: live order board, Accept (ownership lock), sequential status advance incl. "mark paid & close", 60s item edit
  modal, open calls panel with resolve, shift start/end with orders + cash summary, own-orders-only visibility.
- Owner: all cashier views plus menu CRUD with option-group editor, staff create/activate/deactivate, reports
  (day/week/month revenue, order count, avg order value, best/worst sellers, busiest-hours chart), tables & QR codes,
  audit log, settings (name, logo, color, currency, tax, service, table count).
- Verified by the testing agent: 26/26 backend tests pass, customer/cashier/owner frontend flows pass, websocket
  realtime confirmed, RBAC and lifecycle enforcement confirmed.

## Backlog
P0 (next): WebSocket auth/token gating; brute-force lockout on login; append item edits to order `history`.
P1: printable/PDF invoice; kitchen display view; per-item availability toggle from the cashier board; push/sound alert for new orders.
P2: split router modules for server.py; multi-restaurant tenancy; loyalty/discount codes; payment gateway; customer order history by device.
