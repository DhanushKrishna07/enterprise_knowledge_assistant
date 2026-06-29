# Interactive Demo Walkthrough Script

This script guides reviewers through demonstrating the key capabilities of the Enterprise Knowledge Assistant.

## Prerequisites
Ensure the environment is set up and services are running:

1. **Start the application (starts both backend and frontend dev server):**
   ```bash
   npm run dev
   ```
2. Open your browser and navigate to **`http://localhost:5173/`** (or wait for it to open automatically).

---

## Step 1: Login & Navigation
1. Open the login screen on `http://localhost:5173/`. You will see a modern centered card asking for your credentials, along with "Demo accounts" quick-fill chips at the bottom.
2. Click the **Employee** chip (fills `employee@example.com` and password).
3. Click **Sign in**. You will land on the Chat page.
4. Observe the clean layout: sidebar with filters on the left, main conversation area in the center, and a welcome screen proposing common questions.

---

## Step 2: Ingest & Manage Documents (Admin Flow)
1. Click **Sign out** at the bottom-left.
2. Click the **Admin** chip on the login screen and sign in (`admin@example.com`).
3. Note the **Admin Dashboard** button appears in the sidebar. Click it.
4. This loads the dashboard showing:
   - System metrics (indexing sizes, cache hits, avg latencies).
   - Document upload area (drag-and-drop or file selector).
   - List of currently indexed files.
5. In the upload zone, drop a new text or document file (e.g. `Customer_FAQ.md` or a `.docx`). 
6. Once uploaded, the file is automatically written to `data/documents/` and parsed, chunked, and indexed on-the-fly. The list of indexed files will refresh showing the new document.
7. Click the **Delete** button next to any indexed file; verify it disappears from both the index and the physical folder on disk.

---

## Step 3: Ask Policy Questions (Role-Based RAG)
1. Sign out of the admin account, and click the **Employee** chip to log in.
2. Click one of the quick suggestions (e.g. *"What is the leave policy for employees?"*) or type it in.
3. Observe:
   - The plain text response streams in token-by-token.
   - Grounded citations appear as highlighted badges below the answer bubble (e.g. `[1] HR_Policy.docx p.1`).
   - The sources panel opens on the right sidebar detailing the exact text snippets retrieved.
4. Click **👍 Helpful** or **👎 Not helpful** feedback buttons; notice a green toast notification confirms your feedback has been recorded in the database.

---

## Step 4: Access Control Validation
1. Ask a question regarding HR parent policies:
   > *"How many weeks of parental leave does a primary caregiver receive?"*
2. As a `general` employee, notice the system refuses to answer:
   > *"I could not find this information in the available knowledge base."*
   (The document `HR_Policy.docx` requires `hr` department permission or admin permissions).
3. Log out, and log back in as the HR manager (click **HR** chip, or enter `hr@example.com` / `hr123`).
4. Ask the same question:
   > *"How many weeks of parental leave does a primary caregiver receive?"*
5. The system now returns the correct answer: *"16 weeks of paid parental leave"*, citing the protected document sections.
