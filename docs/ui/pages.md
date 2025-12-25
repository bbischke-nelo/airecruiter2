# Web UI Specification

Next.js frontend with TypeScript and Tailwind CSS.

---

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui
- **State**: React Query for server state
- **Forms**: React Hook Form + Zod
- **Charts**: Recharts (optional)

---

## Page Structure

```
app/
├── (auth)/
│   └── login/page.tsx
├── (dashboard)/
│   ├── layout.tsx              # Main nav layout
│   ├── page.tsx                # Dashboard home
│   ├── requisitions/
│   │   ├── page.tsx            # Requisition list
│   │   └── [id]/page.tsx       # Requisition detail
│   ├── applications/
│   │   ├── page.tsx            # Applications list
│   │   └── [id]/page.tsx       # Application detail
│   ├── interviews/
│   │   ├── page.tsx            # Interviews list
│   │   └── [id]/page.tsx       # Interview detail (admin view)
│   ├── queue/page.tsx          # Processing queue
│   ├── logs/page.tsx           # System logs
│   └── settings/
│       ├── page.tsx            # Settings overview
│       ├── credentials/page.tsx
│       ├── prompts/page.tsx
│       ├── personas/page.tsx
│       ├── recruiters/page.tsx
│       └── email/page.tsx
└── interview/
    └── [token]/page.tsx        # Public self-service interview
```

---

## Pages

### 1. Dashboard (`/`)

Overview with key metrics and quick actions.

**Components:**
- Stats cards (total applications, pending, interviews)
- Recent activity feed
- Quick action buttons (manual sync, view queue)
- Health status indicator

**Metrics Displayed:**
- Applications processed (24h, 7d, 30d)
- Interviews completed
- Average risk score
- Queue status

```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard                                            [Settings]│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  45      │  │  12      │  │  8       │  │  0.32    │        │
│  │ Apps/24h │  │ Pending  │  │ Interviews│ │ Avg Risk │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                  │
│  [Sync Now]  [View Queue]  [View Logs]                          │
│                                                                  │
│  Recent Activity                                                 │
│  ├─ 10:30  Application processed: John Doe (Senior Engineer)    │
│  ├─ 10:25  Interview completed: Jane Smith                      │
│  └─ 10:20  Report uploaded: Bob Johnson                         │
│                                                                  │
│  System Status: ● Healthy   Workday: ● Connected                │
└─────────────────────────────────────────────────────────────────┘
```

---

### 2. Requisitions List (`/requisitions`)

Browse and manage job requisitions.

**Features:**
- Search by name, location, recruiter
- Filter: active/inactive, has pending apps
- Sort by: name, created, application count
- Pagination

**Table Columns:**
- Name (link to detail)
- Location
- Recruiter
- Applications (total/pending)
- Auto-send interview toggle
- Active toggle
- Last synced
- Actions (edit, sync, view apps)

---

### 3. Requisition Detail (`/requisitions/[id]`)

View and edit a single requisition.

**Tabs:**
- **Overview**: Basic info, stats, description
- **Applications**: List of applications for this req
- **Settings**: Interview instructions, auto-send config
- **Prompts**: Requisition-specific prompt overrides

**Actions:**
- Edit configuration
- Manual sync
- Send bulk interviews

---

### 4. Applications List (`/applications`)

Browse all candidate applications.

**Filters:**
- Requisition
- Status (new, analyzed, interview_pending, etc.)
- Date range
- Risk score range
- Flags (human requested, compliance review)

**Table Columns:**
- Candidate name
- Requisition
- Status (with badge)
- Risk score (color coded)
- Flags (icons)
- Created date
- Actions (view, reprocess)

---

### 5. Application Detail (`/applications/[id]`)

Full candidate application view.

**Sections:**
1. **Header**: Candidate name, email, requisition, status
2. **Analysis**: Risk score, pros/cons, red flags, suggested questions
3. **Interview**: Status, link to interview detail if exists
4. **Report**: Download link if generated, upload status
5. **Timeline**: Activity log for this application

**Actions:**
- Send interview
- Reprocess
- View in Workday (external link)
- Download report

---

### 6. Interviews List (`/interviews`)

Browse all interviews.

**Filters:**
- Status (scheduled, in_progress, completed, abandoned)
- Requisition
- Date range

**Table Columns:**
- Candidate
- Requisition
- Status
- Started at
- Completed at
- Overall score (if evaluated)
- Actions (view, evaluate)

---

### 7. Interview Detail (`/interviews/[id]`)

Admin view of an interview.

**Sections:**
1. **Header**: Candidate, requisition, status, timestamps
2. **Transcript**: Full conversation with search
3. **Evaluation**: Scores, summary, recommendation
4. **Actions**: Mark complete, request evaluation, download transcript

```
┌─────────────────────────────────────────────────────────────────┐
│  Interview: John Doe - Senior Engineer                          │
│  Status: Completed   Duration: 45 min   Score: 78/100           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Evaluation                                                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Reliability: ████████░░ 8/10                                ││
│  │ Accountability: ███████░░░ 7/10                             ││
│  │ Professionalism: █████████░ 9/10                            ││
│  │ Communication: ████████░░ 8/10                              ││
│  │ Technical: ███████░░░ 7/10                                  ││
│  │ Growth: ████████░░ 8/10                                     ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Recommendation: ● Hire                                          │
│                                                                  │
│  Transcript                                         [Download]   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ AI: Welcome! Let's discuss your experience...               ││
│  │ Candidate: Thank you, I'm excited to be here...             ││
│  │ ...                                                         ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

### 8. Public Interview (`/interview/[token]`)

Candidate self-service interview page.

**Features:**
- No authentication required (token-based)
- Clean, minimal design
- Real-time chat interface
- Progress indicator (if interview has stages)
- "Request Human Contact" button
- Mobile responsive

**States:**
- Loading (validating token)
- Ready (interview available)
- In Progress (actively chatting)
- Completed (thank you message)
- Expired (token expired)
- Error (invalid token)

**Chat Interface:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Interview: Senior Software Engineer                             │
│  ACME Corp                                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ AI ─────────────────────────────────────────────────────────┐
│  │ Hello! Thank you for applying to the Senior Software         │
│  │ Engineer position. I'm here to learn more about your         │
│  │ background and experience.                                   │
│  │                                                              │
│  │ To start, could you tell me about a challenging project      │
│  │ you worked on recently?                                      │
│  └──────────────────────────────────────────────────────────────┘
│                                                                  │
│  ┌─ You ────────────────────────────────────────────────────────┐
│  │ Sure! At my current role, I led the migration of our...      │
│  └──────────────────────────────────────────────────────────────┘
│                                                                  │
│  ┌─ AI ─────────────────────────────────────────────────────────┐
│  │ That's impressive! Can you elaborate on the technical        │
│  │ decisions you made?                                          │
│  └──────────────────────────────────────────────────────────────┘
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐ [Send]    │
│  │ Type your response...                            │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  [Request to Speak with a Human]                                │
└─────────────────────────────────────────────────────────────────┘
```

---

### 9. Processing Queue (`/queue`)

View and manage the processing queue.

**Sections:**
- Pending items
- Running items
- Failed items
- Statistics

**Actions:**
- Add manual job
- Retry failed
- Clear completed
- Clear all

---

### 10. Logs (`/logs`)

System log viewer.

**Filters:**
- Level (DEBUG, INFO, WARNING, ERROR)
- Requisition
- Application
- Date range
- Search text

**Features:**
- Auto-refresh toggle
- Export to CSV
- Color-coded by level

---

### 11. Settings Pages

#### Credentials (`/settings/credentials`)

Workday connection configuration.

**Form Fields:**
- Tenant URL
- Tenant ID
- Client ID
- Client Secret (masked)
- Refresh Token (masked)

**Actions:**
- Test Connection
- Save
- Clear

**Status Display:**
- Connection status
- Last validated
- Token expiry

#### Prompts (`/settings/prompts`)

Manage AI prompts.

**List with:**
- Name
- Type (resume_analysis, interview, etc.)
- Scope (global or requisition-specific)
- Active/Default toggles

**Edit Modal:**
- Name
- Type dropdown
- Template content (code editor)
- JSON schema (optional)
- Description

#### Personas (`/settings/personas`)

Manage interview AI personas.

**List with:**
- Name
- Description
- Active/Default

**Edit Modal:**
- Name
- Description
- System prompt template (code editor)

#### Recruiters (`/settings/recruiters`)

Manage recruiter profiles.

**Form Fields:**
- Name
- Email
- Phone
- Title
- Department
- Public Contact Info (rich text)

#### Email (`/settings/email`)

Email configuration.

**Form Fields:**
- From Address
- From Name
- Provider (SMTP/SES)
- SMTP settings (conditional)

**Actions:**
- Send Test Email
- Save

---

## Design System

### Colors

```css
/* Light theme */
--primary: #2563eb;        /* Blue */
--success: #22c55e;        /* Green */
--warning: #f59e0b;        /* Amber */
--error: #ef4444;          /* Red */
--neutral: #64748b;        /* Slate */

/* Risk score colors */
--risk-low: #22c55e;       /* < 0.3 */
--risk-medium: #f59e0b;    /* 0.3 - 0.6 */
--risk-high: #ef4444;      /* > 0.6 */
```

### Status Badges

| Status | Color | Icon |
|--------|-------|------|
| new | Blue | Circle |
| analyzing | Yellow | Spinner |
| analyzed | Green | Check |
| interview_pending | Purple | Clock |
| interview_in_progress | Purple | Play |
| interview_complete | Green | CheckCheck |
| complete | Green | CheckCircle |
| failed | Red | XCircle |
| skipped | Gray | Minus |

### Typography

- **Headers**: Inter (font-sans)
- **Body**: Inter (font-sans)
- **Code**: JetBrains Mono (font-mono)

---

## Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 640px | Single column, collapsed nav |
| Tablet | 640-1024px | Two column, sidebar |
| Desktop | > 1024px | Full layout |

---

## Real-time Features

### Interview Chat

Use WebSocket for real-time chat:

```typescript
const ws = new WebSocket(`wss://api.example.com/ws/interviews/${token}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'message') {
    appendMessage(message);
  } else if (message.type === 'interview_complete') {
    showCompletionScreen();
  }
};
```

### Queue Updates

Poll or WebSocket for queue status updates:

```typescript
const { data } = useQuery({
  queryKey: ['queue'],
  queryFn: () => fetchQueue(),
  refetchInterval: 5000,  // Poll every 5 seconds
});
```

---

## Accessibility

- WCAG 2.1 AA compliance
- Keyboard navigation support
- Screen reader friendly
- Color contrast ratios met
- Focus indicators visible
