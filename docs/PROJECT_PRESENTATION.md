# Project Presentation Guide

## 30-Second Pitch
ACE e-Counter is a multi-tenant visitor-intake and conversion platform built around a Java Spring Boot application with a Python FastAPI + LangGraph AI/runtime service. It supports public intake, manager-side operations, live handoff, and payment requests in one product flow.

## Live Demo
- Public app: `https://ace-realestate-showcase-production.up.railway.app/`
- Demo org route: `https://ace-realestate-showcase-production.up.railway.app/demo`
- Login: `https://ace-realestate-showcase-production.up.railway.app/login`

## What to Emphasize
- product engineering, not isolated scripts
- clear Java/Python responsibility split
- multi-tenant design
- operational dashboard workflows
- path from visitor intake to conversion

## Suggested Resume Bullets
- Built a multi-tenant visitor-intake and conversion platform with Spring Boot, FastAPI, LangGraph, PostgreSQL, and Stripe-hosted checkout.
- Implemented manager-side dashboard workflows for lead review, takeover, live help, and payment requests.
- Designed a Java application integrated with a separate Python AI/runtime service.
- Delivered a coherent product demo with shared persistence and production-style architecture boundaries.

## Demo Walkthrough
1. Show `README.md`
2. Open `https://ace-realestate-showcase-production.up.railway.app/demo`
3. Open `https://ace-realestate-showcase-production.up.railway.app/login`
4. Open manager dashboard
5. Show lead thread, takeover, live help, and payment request flow
6. Explain Java app vs Python runtime split and the single-container Railway deploy target

## Interview Talking Points
- why Java owns the main product shell
- why Python remains useful for AI/runtime behavior
- how multi-tenancy shapes product design
- why hosted checkout is the right first payment architecture
