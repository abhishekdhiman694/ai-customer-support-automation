import os
import json
import math
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import google.generativeai as genai

app = FastAPI(title="AI Support Automation Hub", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TicketCreate(BaseModel):
    customer_name: str
    email: str
    subject: str
    message: str

class TicketUpdate(BaseModel):
    status: str
    priority: Optional[str] = None
    category: Optional[str] = None
    draft_response: Optional[str] = None

class ArticleCreate(BaseModel):
    title: str
    content: str
    category: str
    tags: List[str]

class ApprovePayload(BaseModel):
    draft_response: str

class SettingsPayload(BaseModel):
    gemini_api_key: Optional[str] = None
    model_name: str = "gemini-1.5-flash"
    temperature: float = 0.2

KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Double Charges and Billing Errors",
        "content": "If you notice a double charge on your credit card statement, it is often a temporary pre-authorization hold. These holds automatically fall off within 3-5 business days depending on your bank. However, if two identical charges are fully captured/posted, please request the customer's transaction IDs or invoice numbers. Once verified, refunds can be processed immediately through Stripe, returning funds to the customer's original payment method within 5-10 business days. Direct customers to email billing@auraglowskincare.com for fast escalations.",
        "category": "Billing",
        "tags": ["double charge", "billing error", "refund", "stripe", "authorization hold"]
    },
    {
        "id": 2,
        "title": "Shipping Times, Tracking and Delays",
        "content": "Standard shipping within the US takes 3-7 business days, while expedited takes 1-3 business days. International shipping takes 7-21 business days and may be subject to customs delays. Once an order is processed, a tracking number is automatically emailed from delivery@auraglowskincare.com. If a package is marked as 'delivered' but the customer cannot find it, advise them to check with neighbors or their local USPS carrier, and wait 24 hours as carriers sometimes scan packages early. If still missing, we will send a free replacement or store credit.",
        "category": "Shipping",
        "tags": ["shipping delay", "tracking number", "missing package", "delivery time"]
    },
    {
        "id": 3,
        "title": "Password Reset and Login Troubleshooting",
        "content": "Users experiencing login issues or password resets not arriving should first check their Spam or Promotions folder. Reset links are sent from accounts@auraglowskincare.com and expire after 2 hours. If the user still doesn't receive the email, verify that their email address is correctly spelled in their profile. If they use Google Auth, they must log in using the 'Sign In with Google' button rather than entering a password. For security reasons, we cannot set passwords manually, but we can send a manual verification code to bypass login temporarily.",
        "category": "Technical",
        "tags": ["password reset", "login failure", "google auth", "verification code", "spam folder"]
    },
    {
        "id": 4,
        "title": "Skincare Compatibility and Sensitive Skin",
        "content": "AuraGlow products are formulated using bio-compatible botanical extracts and mild actives. For sensitive skin, we recommend the Hydrating Aloe Nectar Serum, which is fragrance-free and contains centella asiatica. Always advise customers to perform a patch test on their inner wrist for 24-48 hours before applying any new active (like our Retinol-alternative Bakuchiol Night Oil) to the face. If redness, burning, or irritation occurs, discontinue use immediately, wash the area with cold water, and apply a soothing moisturizer. We offer a 30-day satisfaction guarantee for sensitive skin reactions.",
        "category": "Product Inquiry",
        "tags": ["sensitive skin", "patch test", "allergy", "ingredients", "satisfaction guarantee"]
    },
    {
        "id": 5,
        "title": "Damaged Items on Arrival & Refund Policy",
        "content": "We take quality control seriously, but if items arrive damaged, leaking, or broken, customers are entitled to a full refund or a free replacement. To process this, we require a photo of the damaged product and the shipping box showing the shipping label. The customer does NOT need to return the broken item; they can safely discard it. We will issue refunds immediately upon receiving the photo, which takes 5-10 business days to post to their account. Re-shipments are sent via expedited shipping at no extra cost.",
        "category": "Refund",
        "tags": ["damaged product", "refund policy", "broken bottle", "replacement", "photo proof"]
    }
]

TICKETS_DB: List[Dict[str, Any]] = [
    {
        "id": 101,
        "customer_name": "Marcus Vance",
        "email": "marcus.v@gmail.com",
        "subject": "Charged twice on my last order!",
        "message": "Hi, I checked my bank statement today and I see two charges of $89.00 from AuraGlow for my order yesterday. Only one order went through and I only received one confirmation email. Can you please refund the extra charge immediately? This is very frustrating.",
        "status": "New",
        "priority": "High",
        "sentiment": "Frustrated",
        "category": "Billing",
        "confidence": 0.94,
        "ai_reasoning": "Customer indicates two identical charges of $89 for a single order. Strong signals of irritation ('very frustrating'), warranting High priority. Categorized as Billing due to direct relation to transaction charges.",
        "rag_sources": [KNOWLEDGE_BASE[0]],
        "draft_response": "Dear Marcus,\n\nThank you for reaching out, and I sincerely apologize for the frustration caused by the duplicate charge on your statement.\n\nI have investigated this, and I can confirm that only one order was placed on our system. The second charge of $89.00 is a temporary pre-authorization hold placed by your card issuer to secure the funds. This hold is standard banking practice and will automatically drop off your statement within 3 to 5 business days, depending on your bank's policies.\n\nRest assured, no second charge was finalized. Please monitor your statement, and if the hold does not clear within 5 business days, reply to this email, and our billing team (billing@auraglowskincare.com) will assist you immediately.\n\nWe appreciate your patience.\n\nBest regards,\nAuraGlow Support Team",
        "original_draft": "Dear Marcus,\n\nThank you for reaching out, and I sincerely apologize for the frustration caused by the duplicate charge on your statement...\n",
        "created_at": "2026-06-03T10:15:30Z",
        "approved_by": None,
        "approved_at": None
    },
    {
        "id": 102,
        "customer_name": "Sarah Jenkins",
        "email": "sjenkins92@yahoo.com",
        "subject": "Where is my package? No tracking updates",
        "message": "Hello, my order #48291 was shipped on Friday, but the tracking number hasn't updated in 4 days. It just says 'Label Created' in USPS. Can you tell me where it is and when it will arrive? Thank you.",
        "status": "Processing",
        "priority": "Medium",
        "sentiment": "Neutral",
        "category": "Shipping",
        "confidence": 0.98,
        "ai_reasoning": "Related to tracking information and shipment delays. Tone is neutral. Medium priority because it's a standard delay inquiry within acceptable delivery windows.",
        "rag_sources": [KNOWLEDGE_BASE[1]],
        "draft_response": "Dear Sarah,\n\nThank you for checking in on your order #48291.\n\nI understand it is concerning when tracking details do not update. Standard shipping within the US typically takes 3 to 7 business days. Sometimes, carriers like USPS scan packages late or skip the initial sorting hubs, leaving the status at 'Label Created' until the package arrives at your local post office.\n\nSince your package was shipped on Friday, it has been 2-3 business days. I recommend waiting another 24 to 48 hours for the tracking to update. If you do not see any changes by Friday, please let us know, and we will look into sending a replacement or tracking it down with the carrier.\n\nThank you for your patience.\n\nBest regards,\nAuraGlow Support Team",
        "original_draft": "Dear Sarah,\n\nThank you for checking in on your order #48291...",
        "created_at": "2026-06-03T11:20:00Z",
        "approved_by": None,
        "approved_at": None
    },
    {
        "id": 103,
        "customer_name": "David Thorne",
        "email": "dthorne@techcorp.com",
        "subject": "Can't log in, password reset link not sending",
        "message": "I've clicked the 'Forgot Password' button four times now and I am not receiving any reset emails. I checked my email spelling and it's correct. I need to update my shipping address before my subscription renews tomorrow. Please help.",
        "status": "New",
        "priority": "High",
        "sentiment": "Frustrated",
        "category": "Technical",
        "confidence": 0.91,
        "ai_reasoning": "Customer is locked out of account and has an urgent deadline (subscription renewal tomorrow) requiring high priority. Related to password reset issues (Technical).",
        "rag_sources": [KNOWLEDGE_BASE[2]],
        "draft_response": "Dear David,\n\nThank you for contacting us. I apologize for the difficulty you are experiencing with the password reset link.\n\nPassword reset emails are automatically generated and sent from accounts@auraglowskincare.com. Since you have requested it multiple times, please check your **Spam, Promotions, or Junk folders**, as email servers sometimes filter these automated links. Additionally, note that each link is valid for 2 hours.\n\nTo ensure your subscription renewal tomorrow is updated, please reply directly to this email with your new shipping address. I can manually update it in our database immediately so your next shipment is sent to the correct location.\n\nOnce that is resolved, if you are still unable to log in, let me know, and I can send a temporary login verification code.\n\nBest regards,\nAuraGlow Support Team",
        "original_draft": "Dear David,\n\nThank you for contacting us...",
        "created_at": "2026-06-03T12:05:15Z",
        "approved_by": None,
        "approved_at": None
    },
    {
        "id": 104,
        "customer_name": "Elena Rostova",
        "email": "elena.r@live.com",
        "subject": "Is the Aloe Nectar Serum good for eczema?",
        "message": "Hello, I have very sensitive skin prone to eczema breakouts. I want to buy your Aloe Nectar Serum but I'm worried it might cause a reaction. Is it safe to use or should I buy something else? Thanks!",
        "status": "Resolved",
        "priority": "Low",
        "sentiment": "Positive",
        "category": "Product Inquiry",
        "confidence": 0.97,
        "ai_reasoning": "Product inquiry regarding suitability for eczema/sensitive skin. Low priority since it is a general question before purchase. Positive/inquisitive sentiment.",
        "rag_sources": [KNOWLEDGE_BASE[3]],
        "draft_response": "Dear Elena,\n\nThank you for your interest in our products!\n\nYes, our Hydrating Aloe Nectar Serum is an excellent option for sensitive, eczema-prone skin. It is entirely fragrance-free and formulated with centella asiatica (Cica) and pure aloe, which are highly effective at soothing redness and skin irritation.\n\nFor eczema-prone skin, we always recommend performing a simple patch test before regular use. Apply a small drop of the serum to your inner wrist or behind your ear and observe the area for 24 to 48 hours. If no redness or itching occurs, you can safely apply it to your face.\n\nIf you do buy it and experience any reaction, please know we offer a 30-day satisfaction guarantee on all products, and we will issue a full refund.\n\nLet us know if you have any other questions!\n\nBest regards,\nAuraGlow Support Team",
        "original_draft": "Dear Elena,\n\nThank you for your interest in our products...",
        "created_at": "2026-06-02T15:30:00Z",
        "approved_by": "Alex Mercer",
        "approved_at": "2026-06-02T16:05:00Z"
    },
    {
        "id": 105,
        "customer_name": "Robert Gable",
        "email": "rgable@outlook.com",
        "subject": "BROKEN BOTTLE ON ARRIVAL - PIECE OF GARBAGE",
        "message": "I just opened my box and the Bakuchiol Night Oil bottle is completely smashed! There is oil leaked all over the box and packaging. This was supposed to be a birthday gift for my wife tomorrow and now I have a box of broken glass. I want my money back immediately. This packaging is a joke.",
        "status": "New",
        "priority": "Urgent",
        "sentiment": "Angry",
        "category": "Refund",
        "confidence": 0.99,
        "ai_reasoning": "Customer received a broken glass product causing damage to packaging, and is extremely angry. Demands immediate refund, with tomorrow's birthday deadline making it Urgent priority.",
        "rag_sources": [KNOWLEDGE_BASE[4]],
        "draft_response": "Dear Robert,\n\nI am incredibly sorry to hear that your Bakuchiol Night Oil arrived shattered, and I completely understand your anger, especially since this was meant to be a special gift for your wife tomorrow. This is certainly not the standard of service we aim to provide.\n\nI have issued a full refund of your order immediately. The funds will return to your account in 5-10 business days depending on your bank. Additionally, I would like to arrange for a replacement bottle to be shipped to you via expedited shipping today, free of charge, in hopes it can arrive quickly, or provide a store credit if you prefer.\n\nYou do not need to return the broken bottle. For security/validation, could you please reply with a quick photo of the damaged bottle inside the box? I will log this with our warehouse quality control team to make sure we improve our packaging.\n\nAgain, my sincere apologies for ruining this gift plan. Please let me know if you would like the replacement shipped out right away.\n\nBest regards,\nAuraGlow Support Team",
        "original_draft": "Dear Robert,\n\nI am incredibly sorry to hear that your Bakuchiol Night Oil arrived shattered...",
        "created_at": "2026-06-03T09:40:00Z",
        "approved_by": None,
        "approved_at": None
    }
]

def clean_text(text: str) -> List[str]:
    """Lowercase, strip punctuation, split into tokens, and filter out short words."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()

    stopwords = {"the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "for", "in", "on", "at", "by", "with", "this", "that", "is", "was", "are", "be", "it", "my", "i", "you", "your", "we", "our", "me", "he", "she", "they"}
    return [t for t in tokens if len(t) > 2 and t not in stopwords]

def calculate_rag_matches(query: str, articles: List[Dict[str, Any]], top_k: int = 2) -> List[Dict[str, Any]]:
    """
    Pure Python TF-IDF Cosine Similarity implementation.
    Extremely lightweight, reliable, requires no compilation or local C libraries.
    """
    if not query or not articles:
        return []
    

    query_tokens = clean_text(query)
    doc_tokens_list = [clean_text(art["title"] + " " + art["content"] + " " + " ".join(art["tags"])) for art in articles]
    

    all_tokens = set(query_tokens)
    for dt in doc_tokens_list:
        all_tokens.update(dt)
        
    num_docs = len(articles)
    idf = {}
    for term in all_tokens:

        df = sum(1 for dt in doc_tokens_list if term in dt)

        idf[term] = math.log((1 + num_docs) / (1 + df)) + 1
        

    doc_vectors = []
    for dt in doc_tokens_list:
        vector = {}

        tf = {}
        for term in dt:
            tf[term] = tf.get(term, 0) + 1

        for term, count in tf.items():
            vector[term] = count * idf[term]
        doc_vectors.append(vector)
        

    query_vector = {}
    q_tf = {}
    for term in query_tokens:
        q_tf[term] = q_tf.get(term, 0) + 1
    for term, count in q_tf.items():
        if term in idf:
            query_vector[term] = count * idf[term]
            

    def magnitude(vec):
        return math.sqrt(sum(val ** 2 for val in vec.values()))
    
    query_mag = magnitude(query_vector)
    if query_mag == 0:

        scores = []
        for i, art in enumerate(articles):
            overlap = len(set(query_tokens).intersection(set(doc_tokens_list[i])))
            scores.append((overlap, art))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scores[:top_k] if item[0] > 0]
        
    results = []
    for i, doc_vec in enumerate(doc_vectors):
        doc_mag = magnitude(doc_vec)
        if doc_mag == 0:
            results.append((0.0, articles[i]))
            continue
            

        dot_product = sum(query_vector.get(term, 0) * doc_vec.get(term, 0) for term in query_vector)
        similarity = dot_product / (query_mag * doc_mag)
        results.append((similarity, articles[i]))
        

    results.sort(key=lambda x: x[0], reverse=True)
    

    matches = [item[1] for item in results[:top_k] if item[0] > 0.05]
    return matches

def generate_mock_analysis(subject: str, message: str, matched_kb: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simulates LLM response and metadata based on ticket text and RAG context."""
    text = (subject + " " + message).lower()
    

    category = "Product Inquiry"
    priority = "Low"
    sentiment = "Neutral"
    confidence = 0.88
    
    if any(k in text for k in ["double charge", "charged twice", "billing", "card", "stripe", "invoice", "payment", "price"]):
        category = "Billing"
        priority = "High"
    elif any(k in text for k in ["broken", "smashed", "damaged", "leaking", "cracked", "shattered", "ruined"]):
        category = "Refund"
        priority = "Urgent"
    elif any(k in text for k in ["shipping", "tracking", "usps", "delivery", "delivered", "package", "arrive"]):
        category = "Shipping"
        priority = "Medium"
    elif any(k in text for k in ["password", "login", "reset", "auth", "login failure", "cannot log in"]):
        category = "Technical"
        priority = "High"
    elif any(k in text for k in ["refund", "return", "cancel"]):
        category = "Refund"
        priority = "Medium"
        
    if any(k in text for k in ["angry", "garbage", "joke", "worst", "unacceptable", "smashed", "pissed"]):
        sentiment = "Angry"
        priority = "Urgent" if priority != "Urgent" else "Urgent"
    elif any(k in text for k in ["frustrating", "frustrated", "disappointed", "annoyed", "delay", "waiting"]):
        sentiment = "Frustrated"
    elif any(k in text for k in ["thanks", "thank you", "great", "recommend", "happy"]):
        sentiment = "Positive"
        

    reasoning = f"Mock AI Analysis: Detected category '{category}' and '{sentiment}' sentiment based on key phrases in the message. "
    if priority == "Urgent" or priority == "High":
        reasoning += f"Escalated priority to '{priority}' due to critical issues like system errors, payment problems, or physical product damage."
    else:
        reasoning += f"Assigned '{priority}' priority matching standard customer care SLA guidelines."
        

    kb_info = ""
    if matched_kb:
        kb_info = f"Using information from: '{matched_kb[0]['title']}' FAQ.\n"
        

    first_name = "Customer"

    words = message.split()
    if len(words) > 0 and words[0].lower() in ["hi", "hello", "dear"]:

        if len(words) > 1:
            first_name = words[1].strip(",.!")
            
    draft = f"Dear {first_name},\n\n"
    draft += f"Thank you for reaching out to AuraGlow support. I understand you are contacting us regarding your request: '{subject}'.\n\n"
    
    if category == "Billing":
        draft += "I sincerely apologize for the payment concern. Regarding double charges, this is typically a temporary pre-authorization hold from your bank and should automatically disappear in 3-5 business days.\n\n"
        draft += "If you see two permanent charges posted, please reply with the transaction details and we will issue an immediate refund via Stripe (which clears in 5-10 business days). You can also escalate directly at billing@auraglowskincare.com.\n"
    elif category == "Refund" and "broken" in text or "damaged" in text:
        draft += "I am so sorry to hear that your order arrived damaged. We stand by our products and would be happy to issue a full refund or send an immediate free replacement.\n\n"
        draft += "To complete this refund, could you kindly reply with a photo of the damaged items and the shipping box label? You do not need to ship the broken items back. Refunds take 5-10 business days to post to your bank.\n"
    elif category == "Shipping":
        draft += "I understand you are checking on your tracking details. Domestic shipping typically takes 3-7 business days. Sometimes USPS scans packages early, or updates are delayed. If it says 'Label Created', it is likely in transit and will scan at the local sorting hub shortly.\n\n"
        draft += "We suggest waiting 24-48 hours. If there is still no movement, please let us know and we will issue a replacement package immediately.\n"
    elif category == "Technical":
        draft += "I apologize for the technical difficulties with your login credentials. Our system-generated password reset links are sent from accounts@auraglowskincare.com and expire in 2 hours. Please check your Spam or Promotions folder.\n\n"
        draft += "If you are still unable to log in, please let me know, and I can send you a manual verification code to log in temporarily or update your account details directly.\n"
    elif category == "Product Inquiry" and matched_kb:
        draft += f"Yes, the product is highly suitable. According to our details: {matched_kb[0]['content'][:180]}...\n\n"
        draft += "We recommend doing a small patch test on your wrist for 24-48 hours before regular application. If you have any sensitivity, remember we support a 30-day satisfaction guarantee.\n"
    else:

        if matched_kb:
            draft += f"Based on our knowledge base, we recommend: {matched_kb[0]['content'][:250]}...\n\n"
        else:
            draft += "I have received your support request and logged it with our customer care team. A support agent is currently reviewing your message and will provide a personalized resolution shortly.\n\n"
            
    draft += "\nShould you need anything else, please don't hesitate to ask.\n\nBest regards,\nAuraGlow Support Team"
    
    return {
        "category": category,
        "priority": priority,
        "sentiment": sentiment,
        "confidence": confidence,
        "reasoning": reasoning,
        "draft_response": draft
    }

def generate_gemini_analysis(api_key: str, model_name: str, temp: float, subject: str, message: str, kb_articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calls Gemini API to analyze the support ticket and generate a response."""
    try:
        genai.configure(api_key=api_key)
        

        kb_text = ""
        for i, art in enumerate(kb_articles):
            kb_text += f"Article #{i+1}: {art['title']}\nCategory: {art['category']}\nContent: {art['content']}\nTags: {', '.join(art['tags'])}\n\n"
            
        system_instruction = (
            "You are an advanced AI Customer Support Classifier and Responder for 'AuraGlow' (a natural skincare brand).\n"
            "Your job is to analyze incoming support tickets and return a strict JSON response containing classification, reasoning, and a reply draft.\n"
            "You MUST strictly follow these categories:\n"
            "- Category: Billing, Shipping, Technical, Product Inquiry, Refund, or General\n"
            "- Priority: Low, Medium, High, or Urgent\n"
            "- Sentiment: Positive, Neutral, Frustrated, or Angry\n"
            "The confidence must be a float between 0.0 and 1.0 representing your classification confidence.\n"
            "Use the provided Knowledge Base articles to answer queries accurately. If the articles do not contain the answer, draft a polite response stating you are investigating and will consult a supervisor, but still maintain the classification schema.\n"
            "Draft response must be empathetic, highly professional, clean, and write in the style of customer support.\n"
            "Format your reply as a standard email starting with 'Dear [Name],' and ending with 'Best regards,\\nAuraGlow Support Team'.\n"
            "Ensure the output is valid JSON matching this schema exactly:\n"
            "{\n"
            "  \"category\": \"...\",\n"
            "  \"priority\": \"...\",\n"
            "  \"sentiment\": \"...\",\n"
            "  \"confidence\": 0.95,\n"
            "  \"reasoning\": \"Explain why you chose this category, priority, and sentiment...\",\n"
            "  \"draft_response\": \"Email body goes here...\"\n"
            "}"
        )
        
        prompt = (
            f"--- KNOWLEDGE BASE CONTEXT ---\n{kb_text}\n"
            f"--- SUPPORT TICKET ---\n"
            f"Customer Name: {subject}\n"
            f"Subject: {subject}\n"
            f"Message: {message}\n\n"
            f"Analyze the ticket and generate the JSON response. Do not output markdown code blocks (e.g. ```json), just raw JSON."
        )
        

        actual_model = model_name
        if "gemini" not in actual_model.lower():
            actual_model = "gemini-1.5-flash"
            
        model = genai.GenerativeModel(
            model_name=actual_model,
            generation_config={
                "temperature": temp,
                "response_mime_type": "application/json",
            },
            system_instruction=system_instruction
        )
        
        response = model.generate_content(prompt)

        result = json.loads(response.text.strip())
        return result
    except Exception as e:

        fallback = generate_mock_analysis(subject, message, kb_articles)
        fallback["reasoning"] = f"Gemini API Error (Fell back to local rules): {str(e)}"
        return fallback

@app.get("/api/tickets")
def get_tickets():
    """Return all tickets, sorted by ID descending."""
    return sorted(TICKETS_DB, key=lambda x: x["id"], reverse=True)

@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    """Retrieve details for a single ticket."""
    for t in TICKETS_DB:
        if t["id"] == ticket_id:
            return t
    raise HTTPException(status_code=404, detail="Ticket not found")

@app.post("/api/tickets")
def create_ticket(ticket: TicketCreate, x_api_key: Optional[str] = Header(None, alias="X-Gemini-Key"), x_model: Optional[str] = Header("gemini-1.5-flash", alias="X-Model-Name"), x_temp: Optional[float] = Header(0.2, alias="X-Temperature")):
    """Submit a new support ticket and run the RAG + AI pipeline immediately."""
    new_id = max(t["id"] for t in TICKETS_DB) + 1 if TICKETS_DB else 101
    

    matched_articles = calculate_rag_matches(ticket.subject + " " + ticket.message, KNOWLEDGE_BASE)
    

    if x_api_key:
        ai_res = generate_gemini_analysis(
            api_key=x_api_key,
            model_name=x_model,
            temp=x_temp,
            subject=ticket.subject,
            message=ticket.message,
            kb_articles=matched_articles
        )
    else:
        ai_res = generate_mock_analysis(ticket.subject, ticket.message, matched_articles)
        
    new_ticket = {
        "id": new_id,
        "customer_name": ticket.customer_name,
        "email": ticket.email,
        "subject": ticket.subject,
        "message": ticket.message,
        "status": "New",
        "priority": ai_res.get("priority", "Medium"),
        "sentiment": ai_res.get("sentiment", "Neutral"),
        "category": ai_res.get("category", "General"),
        "confidence": ai_res.get("confidence", 0.90),
        "ai_reasoning": ai_res.get("reasoning", "Classified automatically by system heuristics."),
        "rag_sources": matched_articles,
        "draft_response": ai_res.get("draft_response", ""),
        "original_draft": ai_res.get("draft_response", ""),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "approved_by": None,
        "approved_at": None
    }
    
    TICKETS_DB.append(new_ticket)
    return new_ticket

@app.post("/api/tickets/{ticket_id}/analyze")
def analyze_ticket(ticket_id: int, payload: SettingsPayload):
    """Trigger re-analysis of an existing ticket using specified model parameters."""
    ticket = None
    for t in TICKETS_DB:
        if t["id"] == ticket_id:
            ticket = t
            break
            
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        

    matched_articles = calculate_rag_matches(ticket["subject"] + " " + ticket["message"], KNOWLEDGE_BASE)
    

    if payload.gemini_api_key:
        ai_res = generate_gemini_analysis(
            api_key=payload.gemini_api_key,
            model_name=payload.model_name,
            temp=payload.temperature,
            subject=ticket["subject"],
            message=ticket["message"],
            kb_articles=matched_articles
        )
    else:
        ai_res = generate_mock_analysis(ticket["subject"], ticket["message"], matched_articles)
        
    ticket["priority"] = ai_res.get("priority", ticket["priority"])
    ticket["sentiment"] = ai_res.get("sentiment", ticket["sentiment"])
    ticket["category"] = ai_res.get("category", ticket["category"])
    ticket["confidence"] = ai_res.get("confidence", ticket["confidence"])
    ticket["ai_reasoning"] = ai_res.get("reasoning", ticket["ai_reasoning"])
    ticket["rag_sources"] = matched_articles
    ticket["draft_response"] = ai_res.get("draft_response", ticket["draft_response"])
    
    return ticket

@app.post("/api/tickets/{ticket_id}/approve")
def approve_ticket(ticket_id: int, payload: ApprovePayload):
    """Approve and sign off a support draft. Status shifts to Resolved."""
    for t in TICKETS_DB:
        if t["id"] == ticket_id:
            t["status"] = "Resolved"
            t["draft_response"] = payload.draft_response
            t["approved_by"] = "Alex Mercer (Agent)"
            t["approved_at"] = datetime.utcnow().isoformat() + "Z"
            return t
    raise HTTPException(status_code=404, detail="Ticket not found")

@app.get("/api/kb")
def get_kb():
    """Get all knowledge base articles."""
    return KNOWLEDGE_BASE

@app.post("/api/kb")
def create_kb_article(article: ArticleCreate):
    """Add a new article to the knowledge base."""
    new_id = max(a["id"] for a in KNOWLEDGE_BASE) + 1 if KNOWLEDGE_BASE else 1
    new_article = {
        "id": new_id,
        "title": article.title,
        "content": article.content,
        "category": article.category,
        "tags": article.tags
    }
    KNOWLEDGE_BASE.append(new_article)
    return new_article

@app.delete("/api/kb/{article_id}")
def delete_kb_article(article_id: int):
    """Delete a knowledge base article."""
    global KNOWLEDGE_BASE
    initial_len = len(KNOWLEDGE_BASE)
    KNOWLEDGE_BASE = [a for a in KNOWLEDGE_BASE if a["id"] != article_id]
    if len(KNOWLEDGE_BASE) == initial_len:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"detail": "Article deleted successfully"}

@app.get("/api/analytics")
def get_analytics():
    """Generate metrics for dashboards."""
    total_tickets = len(TICKETS_DB)
    resolved_tickets = sum(1 for t in TICKETS_DB if t["status"] == "Resolved")
    new_tickets = sum(1 for t in TICKETS_DB if t["status"] == "New")
    processing_tickets = sum(1 for t in TICKETS_DB if t["status"] == "Processing")
    escalated_tickets = sum(1 for t in TICKETS_DB if t["status"] == "Escalated")
    

    categories = {}
    for t in TICKETS_DB:
        cat = t["category"]
        categories[cat] = categories.get(cat, 0) + 1
        

    sentiments = {}
    for t in TICKETS_DB:
        sent = t["sentiment"]
        sentiments[sent] = sentiments.get(sent, 0) + 1
        

    priorities = {}
    for t in TICKETS_DB:
        prio = t["priority"]
        priorities[prio] = priorities.get(prio, 0) + 1
        

    avg_human_cost = 1.50
    avg_ai_cost = 0.002
    cost_saved = resolved_tickets * (avg_human_cost - avg_ai_cost)
    

    automation_rate = (resolved_tickets / total_tickets * 100) if total_tickets > 0 else 0.0
    

    model_comparison = [
        {"model": "Gemini 2.0 Flash", "cost_per_1k_in": 0.000075, "cost_per_1k_out": 0.0003, "avg_latency": "0.6s", "accuracy": "High"},
        {"model": "Gemini 1.5 Pro", "cost_per_1k_in": 0.00125, "cost_per_1k_out": 0.00375, "avg_latency": "1.8s", "accuracy": "Exceptional"},
        {"model": "Claude 3.5 Sonnet", "cost_per_1k_in": 0.003, "cost_per_1k_out": 0.015, "avg_latency": "2.1s", "accuracy": "Exceptional"},
        {"model": "GPT-4o", "cost_per_1k_in": 0.005, "cost_per_1k_out": 0.015, "avg_latency": "1.5s", "accuracy": "Very High"}
    ]
    
    return {
        "summary": {
            "total": total_tickets,
            "resolved": resolved_tickets,
            "new": new_tickets,
            "processing": processing_tickets,
            "escalated": escalated_tickets,
            "automation_rate": round(automation_rate, 1),
            "cost_saved_usd": round(cost_saved, 2)
        },
        "by_category": categories,
        "by_sentiment": sentiments,
        "by_priority": priorities,
        "model_comparison": model_comparison
    }

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
