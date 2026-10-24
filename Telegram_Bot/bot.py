from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import pandas as pd
from project_functions import process_user_input, column_name_fa

import matplotlib.pyplot as plt
import io
import arabic_reshaper
from bidi.algorithm import get_display


# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *راهنمای استفاده از ربات*\n\n"
        "🔎 `/start`  → گفتگو با من و شروع جستجو\n"
        "ℹ️ `/help` → مشاهده این راهنما\n\n"
        "🔹 *مثال‌هایی که می‌تونی امتحان کنی:*\n"
        "- یک خانه سه خوابه در الهیه تهران با آسانسور و بالکن می‌خواهم\n"
        "- من یک خونه میخوام توی مشهد توی محله قاسم آباد، حداقل دوتا اتاق داشته باشه و قیمت زیر 2 میلیارد\n"
        "- آپارتمان در اصفهان با پارکینگ و طبقه دوم\n\n"
        "🔹 *فیلدهایی که می‌تونی مشخص کنی:*\n"
        "🏙 شهر\n"
        "📍 محله\n"
        "💰 قیمت\n"
        "📐 زیربنا (متر مربع)\n"
        "🛏 تعداد اتاق\n"
        "🏢 طبقه\n"
        "🌿 بالکن\n"
        "🛗 آسانسور\n"
        "📦 انبار\n"
        "🚗 پارکینگ\n"
        "🚿 تامین‌کننده آب گرم\n"
        "📅 سال ساخت\n"
        "📜 نوع سند\n"
        "🔥 سیستم گرمایشی\n"
        "❄️ سیستم سرمایشی\n"
        "🚽 نوع سرویس بهداشتی\n"
        "🧭 جهت ساختمان\n"
        "🪵 جنس کف\n"
        "🏬 تعداد کل طبقات\n"
        "🔢 تعداد واحد در هر طبقه\n"
        "🛠 بازسازی شده یا نه\n\n"
        "در صورتی که هیچ نتیجه ای برای سرچت پیدا نشد، برای فیلد هایی مثل قیمت و تعداد اتاق و ... (فیلد های عددی) میتونی بازه مشخص کنی.\n"
        "من اطلاعات رو می‌گیرم و در صورت نیاز ویژگی‌های بیشتری رو می‌پرسم تا نتایج مناسبی پیدا کنم. 🫡",
        parse_mode="Markdown"
    )



user_states = {}  # user_id -> {"history": str, "counter": int}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_states[user_id] = {"history": "", "counter": 0}  # clearing history
    samples = [
        "یک خانه سه خوابه در الهیه تهران با آسانسور و بالکن می‌خواهم. شوفاژ هم داشته باشه",
        "یک خونه در مشهد میخوام، محله سناباد که پارکینگ داشته باشه با آسانسور و بین دو تا 5 اتاق", # بجای راهنمایی
        "آپارتمان در اصفهان با پارکینگ و طبقه دوم و قیمتش زیر دو میلیارد باشه"
    ]
    keyboard = [
        [KeyboardButton("/start"), KeyboardButton("/help")],
        *[[KeyboardButton(text=s)] for s in samples]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "سلام ^_^\nمن اینجام تا برات خونه‌های مناسب پیدا کنم.\nهر ویژگی که مدنظرت هست رو بهم بگو (مثلاً شهر، محله، قیمت، پارکینگ، آسانسور، طبقه و...).\nوقتی حداقل ۴ ویژگی رو گفتی، نتایج رو نشون میدم. 🏠\nاگر میخوای کامل ویژگی ها و نمونه ورودی هارو ببینی /help رو بزن.",
        reply_markup=reply_markup
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_text = update.message.text.strip()
    # If this user has no state yet (first message or after /start)
    if user_id not in user_states or not user_states[user_id]["history"]:
        user_states[user_id] = {"history": user_text, "counter": 1}
    else:
        user_states[user_id]["history"] += ". " + user_text
        user_states[user_id]["counter"] += 1
    combined_text = user_states[user_id]["history"].strip()
    answer, df_results = process_user_input(user_id, combined_text, user_states)
    await update.message.reply_text(answer)

    if not df_results.empty:
        context.user_data['last_df_results'] = df_results.copy()

        keyboard = [
            [InlineKeyboardButton("🔄 بدون مرتب‌سازی", callback_data="sort_none")],
            [InlineKeyboardButton("💰 قیمت", callback_data="sort_price_value")],
            [InlineKeyboardButton("📐 زیربنا", callback_data="sort_building_size")],
            [InlineKeyboardButton("🛏 تعداد اتاق", callback_data="sort_rooms_count")],
            [InlineKeyboardButton("⬆️ طبقه", callback_data="sort_floor")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🔎 لطفاً مرتب‌سازی نتایج را انتخاب کنید:", reply_markup=reply_markup)


SORT_LABELS = {
    "none": "بدون مرتب‌سازی",
    "price_value": "قیمت",
    "building_size": "زیربنا",
    "rooms_count": "تعداد اتاق",
    "floor": "طبقه",
}

async def sort_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    await query.answer()

    df_results = context.user_data.get("last_df_results")
    if df_results is None or df_results.empty:
        await query.edit_message_text("❌ هیچ نتیجه‌ای وجود ندارد.")
        return

    sort_field = query.data.replace("sort_", "")
    label = SORT_LABELS.get(sort_field, sort_field)

    # sorting logic
    if sort_field in df_results.columns and sort_field != "none":
        # only price and floor ascending
        if sort_field in ["price_value", "floor"]:
            df_results = df_results.sort_values(by=sort_field, ascending=True)
        
        if sort_field in ["rooms_count", "building_size"]:
            df_results = df_results.sort_values(by=sort_field, ascending=False)

    context.user_data['last_df_results'] = df_results
    context.user_data['last_df_pointer'] = 0  # reset pointer for next 5 results
    context.user_data['last_df_indexes'] = list(df_results.index)  # <-- saving indexes


    await query.edit_message_text(f"✅ {len(df_results)} نتیجه پیدا شد (مرتب‌سازی: {label}).")
    await show_next_results(update, context)  # show first 5 results

    keyboard = [
        [
            InlineKeyboardButton("📋 دریافت ایندکس‌ها", callback_data="show_indexes"),
            InlineKeyboardButton("➡️ ۵ نتیجه بعدی", callback_data="show_next_5"),
            InlineKeyboardButton("📊 نمودار قیمت‌ها", callback_data="show_price_chart")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("گزینه‌ها:", reply_markup=reply_markup)
    
    user_states[user_id] = {"history": "", "counter": 0}  # clearing after results


async def show_price_chart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    df_results = context.user_data.get("last_df_results")
    if df_results is None or df_results.empty or "price_value" not in df_results.columns:
        await query.message.reply_text("❌ داده‌ای برای رسم نمودار قیمت‌ها موجود نیست.")
        return
    
    # ensuring numeric values
    df_results['price_value'] = pd.to_numeric(df_results['price_value'], errors='coerce')
    df_results = df_results.dropna(subset=['price_value'])
    
    if df_results.empty:
        await query.message.reply_text("❌ داده‌ی معتبری برای نمودار قیمت‌ها وجود ندارد.")
        return

    xlabel = get_display(arabic_reshaper.reshape("قیمت"))
    ylabel = get_display(arabic_reshaper.reshape("تعداد آگهی‌ها"))
    title  = get_display(arabic_reshaper.reshape("نمودار توزیع قیمت‌ها"))

    plt.figure(figsize=(6,4))
    df_results['price_value'].plot(kind='hist', bins=10, color='#296b73', edgecolor='black')
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    
    # saving the plot to in-memory buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
  
    await query.message.reply_photo(photo=buf) # send image via Telegram


async def show_next_results(update: Update, context: ContextTypes.DEFAULT_TYPE, show_desc=True):
    query = update.callback_query
    if query:
        await query.answer()
        df_results = context.user_data.get("last_df_results")
        pointer = context.user_data.get("last_df_pointer", 0)
        if df_results is None or df_results.empty:
            await query.message.reply_text("❌ هیچ نتیجه‌ای وجود ندارد.")
            return
        start = pointer
        end = min(pointer + 5, len(df_results))
        preview = df_results.iloc[start:end]

        for idx, row in preview.iterrows():
            lines = []
            for col in ['city_slug','neighborhood_slug','price_value','building_size','rooms_count','floor']:
                if col in df_results.columns:
                    lines.append(f"{column_name_fa[col]}: {row[col]}")
            summary = "\n".join(lines)
            await query.message.reply_text(f"▫️شماره {idx}:\n{summary}")

        # showing descriptions only for first batch
        if show_desc:
            for i, row in enumerate(preview[['description']].itertuples(), start=1):
                desc = str(row.description).replace("\r\n", "\n").strip()
                await query.message.reply_text(f"📌 آگهی {start + i}:\n{desc}")

        context.user_data['last_df_pointer'] = end
        if end >= len(df_results):
            await query.message.reply_text("✅ دیگه نتیجه‌ای برای نمایش نیست.")


async def show_next_5_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_next_results(update, context, show_desc=False) # and not showing description


async def show_indexes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    indexes = context.user_data.get('last_df_indexes', [])
    
    if indexes:
        if len(indexes) > 100:
            await query.message.reply_text(f"ایندکس‌های نتایج: {indexes[:100]} و {len(indexes) - 100} ایندکس دیگر")
        else:
            await query.message.reply_text(f"ایندکس‌های نتایج: {indexes}")
    else:
        await query.message.reply_text("نتیجه‌ای برای نمایش ایندکس وجود ندارد.")

def main():
    application = Application.builder().token("8055467518:AAHc2jYb9yeROrYrmTJjq3VZ_F_2LRdMgoo").build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(show_indexes_callback, pattern="^show_indexes$"))
    application.add_handler(CallbackQueryHandler(sort_results, pattern="^sort_"))
    application.add_handler(CallbackQueryHandler(show_next_5_callback, pattern="^show_next_5$"))
    application.add_handler(CallbackQueryHandler(show_price_chart_callback, pattern="^show_price_chart$"))

    application.run_polling()

if __name__ == "__main__":
    main()

