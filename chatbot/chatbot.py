#6918204649:AAGP-uIfNoziXXN-ueYXHD7kMJ3NJ566BUk 

import os
import spacy
import telegram
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext, filters, ContextTypes
from spacy.lang.en.stop_words import STOP_WORDS
from string import punctuation
from heapq import nlargest

from workers import PDFtoQuestions
from .messages import *



class ChatBot:
    def __init__(self, TOKEN: str) -> None:
        print('Bot starting..')
        self.app = Application.builder().token(TOKEN).build()

        #commands
        self.app.add_handler(CommandHandler('start', self.start_command))
        self.app.add_handler(CommandHandler('help', self.help_command))
        self.app.add_handler(CommandHandler('custom', self.custom_command))

        self.app.add_handler(MessageHandler(filters.TEXT, self.handle_message))
        self.app.add_handler(MessageHandler(filters.Document.PDF, callback=self.handle_file))
        self.app.add_handler(MessageHandler(filters=~ filters.Document.MimeType('application/pdf'), callback=self.handle_other_file))
        self.app.add_handler(CallbackQueryHandler(self.generate_questions))

        #error
        self.app.add_error_handler(self.error)


    #Commands
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_chat_action(update.effective_chat.id, action=constants.ChatAction.TYPING)
        await update.message.reply_text(START_TEXT)
        await context.bot.set_my_commands([BotCommand("start", "Restart the bot"), BotCommand("help", "Help description")])


    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text('Hello! Please type something so I can help you.')


    async def custom_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text('this is a custom command')


    #Responses
    def handle_response(self, text: str) -> str:
        text_input: str = text.lower()

        if 'hello' in text_input:
            return 'Hello! How can I help you today?'
        #add nlp so that it can understand the text and give a response
        elif 'pdf' in text_input:
            return INSTRUCTION_TEXT
        elif text_input:
            text_to_summarize = text_input

            summary = self.text_summarization(text_to_summarize, 0.3)
            return f'Summarization of the text:\n{summary}'
    
        return "I'm not sure how to respond to that."
        
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE): 
        text: str = update.message.text
        response: str = self.handle_response(text)
        print("Bot:", response)
        await update.message.reply_text(response)

    

    async def handle_other_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            filename = update.message.document.file_name.split(".")
            extension = filename[len(filename)-1]
            await update.message.reply_text(text=WRONG_FILE.format(extension), parse_mode=constants.ParseMode.HTML)
        except AttributeError as e:
            await update.message.reply_text("Sorry Bot can't Read this file\n\nTry Sending the file with ```.pdf``` Extension",parse_mode=constants.ParseMode.MARKDOWN_V2)

    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE): 
        keyboard = [[InlineKeyboardButton(text="Generate Questions 📋", callback_data="generate")], [
                     InlineKeyboardButton(text="Get Images 📷", callback_data="idk")]]
        await update.message.reply_document(document=update.message.document, caption="Click On 👇 to Generate Questions", reply_markup=InlineKeyboardMarkup(keyboard))

    async def generate_questions(self, update: Update, context: ContextTypes.DEFAULT_TYPE): 
        try: 
            filename = r"chatbot\uploads\file"+str(update.effective_chat.id)+".pdf"
            file_id = update.callback_query.message.document.file_id
            docs = await context.bot.get_file(file_id=file_id)
            # Ensure file_id is not None
            if not file_id:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to retrieve file ID.")
                return
            
            docs = await context.bot.get_file(file_id=file_id)
            
            # Check if file retrieval was successful
            if not docs:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to download the file.")
                return

            await docs.download_to_drive(custom_path=filename)
            await context.bot.answer_callback_query(update.callback_query.id, text="Processing the file...")
            
            if update.callback_query.data == "generate":
                pdf = PDFtoQuestions(filename)
                quests = pdf.extract_questions(2)  

                await self.show_questions(update, context, quests)

                
                
            elif update.callback_query.data == "idk":
                await context.bot.send_message(update.effective_chat.id, text="IDK WHY")
            else:
                await context.bot.send_message(update.effective_chat.id, text="NONENONENONE")

            # os.remove(filename)
        except Exception as e:
            # Log the error and inform the user
            print(f"An error occurred: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred while processing your request. Please try again later.")


    async def show_questions(self, update: Update, context: ContextTypes.DEFAULT_TYPE, questions): 
        for index, question_data in questions.items():
            keyboard = []
            reply_markup = None
            qa_text = f"QUESTION #{index}\n{question_data['question']}\nAnswer: {question_data['answer']}\n"
            
            if 'choices' in question_data:
                for choice_number, choice_text in question_data['choices'].items():
                    keyboard.append([InlineKeyboardButton(text=choice_text, callback_data=choice_text)])
                reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(chat_id=update.effective_chat.id, text=QUESTION_TEXT.format(qa_text), parse_mode=constants.ParseMode.HTML, reply_markup=reply_markup)
            await self.check_answer(update, context, question_data['answer'])


    async def check_answer(self, update: Update, context: CallbackContext, correct_answer: str):
        chosen_choice = update.callback_query.data
        print("chosen:", chosen_choice)
        #await query.answer()
        text = "correct" if chosen_choice == correct_answer else "wrong"
        
        response: str = self.handle_response(text)
        print("Bot:", response)
        await update.message.reply_text(response)



    #summarization of the text
    def text_summarization(self, text, percentage):

        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text) 

        tokens=[token.text for token in doc]
        # print("unused tokens:", tokens)
        frequency = dict()

        #cleaning text
        for word in doc:
            if word.text.lower() not in list(STOP_WORDS):
                if word.text.lower() not in punctuation:
                    if word.text not in frequency.keys():
                        frequency[word.text] = 1
                    else:
                        frequency[word.text] += 1

        #print("Freq:", frequency)
        #setting max frequency of word
        max_frequency = max(frequency.values())

        #normalization
        for word in frequency.keys():
            frequency[word] = frequency[word]/max_frequency

        #sentence is weighed based on how often it contains the token
        sent_tokens = [sent for sent in doc.sents]
        #print("SentTokens:", sent_tokens)

        sentscore = dict()
        for sent in sent_tokens:
            for word in sent:
                if word.text.lower() in frequency.keys():
                    if sent not in sentscore.keys():
                        sentscore[sent] = frequency[word.text.lower()]
                    else:
                        sentscore[sent] += frequency[word.text.lower()]

        len_tokens = int(len(sent_tokens)*percentage)

        #Summary for the sentences with maximum score. 
        #Here, each sentence in the list is of spacy.span type
        summary = nlargest(n = len_tokens, iterable = sentscore, key = sentscore.get)

        #preparation for final summary
        final_summary = [word.text for word in summary] 
        
        #string convert
        summary = ' '.join(final_summary)

        return summary



    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(f'Update {update} caused error {context.error}')

