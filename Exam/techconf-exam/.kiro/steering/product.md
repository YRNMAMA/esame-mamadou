# TechConf — Product Overview

## Domain

TechConf is a platform for organizing and managing technical conferences (cloud, AI, security). The platform manages:

- **Users**: Attendees, speakers, and organizers
- **Events**: Conferences with lifecycle (draft → published → cancelled), capacity, and pricing
- **Registrations**: User enrollments in events with capacity enforcement
- **Feedback** (optional): Ratings and comments from registered attendees
- **Notifications** (optional): Messages to users, including broadcasts to event registrants

## Service Boundaries

| Service | Responsibility | Port |
|---------|---------------|------|
| user-service | User registry (CRUD, unique email, roles) | 5001 |
| event-service | Event lifecycle, organizer validation via user-service | 5002 |
| registration-service | Registrations, capacity checks, stats | 5003 |
| feedback-service | Event ratings from confirmed registrants | 5004 |
| notification-service | User notifications and event broadcasts | 5005 |

## Key Business Rules

- Email uniqueness is case-insensitive
- Events must have an organizer with role=organizer
- Only published events accept registrations
- Capacity is enforced; cancellations free seats
- Feedback only from confirmed registrants
- Notifications broadcast only to confirmed registrants