# Implementation Plan: MedFlow Clinical Trial Coordination System

## Overview

This implementation plan breaks down the MedFlow multi-agent clinical trial coordination system into 6 phases over 14 weeks. The system will be built using Python and AWS AgentCore Runtime with the Strands framework. Each phase delivers testable functionality and builds incrementally on previous phases to manage complexity.

**Note:** This is a tech demo implementation using a single AWS environment for demonstration purposes.

## Tasks

### Phase 1: Foundation (Weeks 1-2)

- [x] 1. Set up AWS infrastructure and development environment
  - Configure IAM roles and policies for AgentCore Runtime (single demo environment)
  - Set up Python virtual environment with required dependencies
  - Configure logging infrastructure (CloudWatch Logs)
  - Create base project structure with agent directories
  - _Requirements: 11.1, 19.1_

- [x] 2. Configure AgentCore Gateway for REST API transformation
  - [x] 2.1 Implement Gateway configuration for EHR API
    - Define MCP tool schemas for `get_patient_record` and `get_lab_results`
    - Configure REST endpoint mappings and authentication
    - Write Python client wrapper for Gateway-transformed tools
    - _Requirements: 9.1, 9.2, 9.4_
  
  - [x] 2.2 Implement Gateway configuration for insurance provider APIs
    - Define MCP tool schema for `submit_authorization_request`
    - Configure OAuth authentication via AgentCore Identity
    - Write Python client wrapper for insurance API tools
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [x] 2.3 Write unit tests for Gateway integration
    - Test successful API transformation
    - Test authentication handling
    - Test error response parsing
    - _Requirements: 9.5_

- [x] 3. Implement basic Orchestrator Agent with Agent-as-Tool pattern
  - [x] 3.1 Create Orchestrator Agent core structure
    - Implement request parsing for all 6 request types
    - Define input/output interfaces (CoordinationRequest, CoordinationResponse)
    - Set up AgentCore Runtime execution environment
    - Implement basic logging and audit trail
    - _Requirements: 1.1, 1.2, 19.1_
  
  - [x] 3.2 Implement Agent-as-Tool invocation pattern
    - Create tool invocation methods for each specialist agent
    - Implement result aggregation from multiple specialist agents
    - Add error handling and failure logging
    - _Requirements: 1.3, 1.4, 1.5_
  
  - [x] 3.3 Write property test for request routing
  - [x] 3.4 Write property test for result aggregation
  - [x] 3.5 Write property test for failure handling

- [x] 4. Create mock specialist agents for integration testing
  - Implement mock Patient Eligibility Agent returning test eligibility reports
  - Implement mock Adverse Event Monitor returning test event detections
  - Implement mock Regulatory Report Agent returning test report metadata
  - Implement mock Insurance Authorization Agent returning test authorization decisions
  - Implement mock Patient Communication Agent returning test conversation summaries
  - Implement mock Trial Coordinator Agent returning test schedules
  - _Requirements: 1.3, 1.4_

- [x] 5. Checkpoint - Verify foundation infrastructure
  - Ensure all tests pass, ask the user if questions arise.

### Phase 2: Core Specialist Agents (Weeks 3-5)

- [x] 6. Implement Patient Eligibility Agent with Bedrock Knowledge Base
  - [x] 6.1 Set up Bedrock Knowledge Base integration
  - [x] 6.2 Implement eligibility screening logic
  - [x] 6.3 Implement semantic search and citation generation
  - [x] 6.4 Write property test for criteria completeness
  - [x] 6.5 Write property test for citation inclusion
  - [x] 6.6 Write unit tests for Patient Eligibility Agent

- [x] 7. Implement Regulatory Report Agent with Lambda PDF generation
  - [x] 7.1 Create Lambda function for PDF generation
    - Write Python Lambda function using ReportLab library
    - Implement PDF generation for FDA 21 CFR Part 312 format
    - Implement PDF generation for EMA ICH-GCP format
    - Configure Lambda with 3GB memory and 30s timeout
    - Deploy Lambda with required layers (reportlab, pillow)
    - _Requirements: 15.1, 15.3_
  
  - [x] 7.2 Implement Regulatory Report Agent core logic
    - Create RegulatoryReportRequest and RegulatoryReportResponse data models
    - Implement report format selection based on regulatory body
    - Use Gateway to access internal document APIs
    - Query external regulatory databases for reference data
    - Implement section completeness validation
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_
  
  - [x] 7.3 Implement Lambda invocation and PDF handling
    - Invoke Lambda function with structured report data
    - Validate returned PDF format
    - Implement retry logic (up to 2 retries)
    - Handle missing data and generate missing elements list
    - _Requirements: 4.4, 4.7, 15.2, 15.4, 15.5_
  
  - [x]* 7.4 Write property test for format selection
    - **Property 10: Regulatory Report Format Selection**
    - **Validates: Requirements 4.1**
  
  - [x]* 7.5 Write property test for section completeness
    - **Property 11: Regulatory Report Section Completeness**
    - **Validates: Requirements 4.5**
  
  - [x]* 7.6 Write property test for missing data reporting
    - **Property 12: Missing Data Reporting**
    - **Validates: Requirements 4.7**
  
  - [x]* 7.7 Write property test for Lambda data structure
    - **Property 28: Regulatory Report Lambda Data Structure**
    - **Validates: Requirements 15.2**
  
  - [x]* 7.8 Write property test for PDF validation
    - **Property 29: PDF Validation**
    - **Validates: Requirements 15.4**
  
  - [x]* 7.9 Write property test for PDF generation retry
    - **Property 30: PDF Generation Retry**
    - **Validates: Requirements 15.5**
  
  - [x]* 7.10 Write unit tests for Regulatory Report Agent
    - Test FDA report format selection
    - Test EMA report format selection
    - Test section completeness validation
    - Test edge case: report with all sections complete
    - Test edge case: report with all sections incomplete

- [x] 8. Implement Insurance Authorization Agent with Policy and Identity
  - [x] 8.1 Configure AgentCore Policy with Cedar policies
    - Define natural language authorization rules
    - Configure AgentCore Policy to auto-convert to Cedar format
    - Set up policy enforcement at tool call level
    - Configure 100ms evaluation timeout
    - _Requirements: 10.1, 10.2, 10.3, 10.6_
  
  - [x] 8.2 Configure AgentCore Identity for OAuth
    - Set up OAuth provider configurations for insurance APIs
    - Configure token lifecycle management (refresh, expiration)
    - Implement token caching and refresh logic
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
  
  - [x] 8.3 Implement Insurance Authorization Agent core logic
    - Create AuthorizationRequest and AuthorizationResponse data models
    - Implement cost-based routing logic ($500, $5000 thresholds)
    - Integrate with AgentCore Policy for rule evaluation
    - Integrate with AgentCore Identity for OAuth tokens
    - Call insurance provider APIs via Gateway with OAuth tokens
    - Implement retry logic with token refresh (up to 3 retries)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_
  
  - [x]* 8.4 Write property test for cost-based routing
    - **Property 13: Authorization Cost-Based Routing**
    - **Validates: Requirements 5.3, 5.4, 5.5**
  
  - [x]* 8.5 Write property test for OAuth token inclusion
    - **Property 14: Authorization API Token Inclusion**
    - **Validates: Requirements 5.7**
  
  - [x]* 8.6 Write property test for policy enforcement
    - **Property 15: Authorization Policy Enforcement**
    - **Validates: Requirements 5.8**
  
  - [x]* 8.7 Write property test for retry on auth failure
    - **Property 16: Authorization Retry on Auth Failure**
    - **Validates: Requirements 5.9**
  
  - [x]* 8.8 Write unit tests for Insurance Authorization Agent
    - Test auto-approval for $499 procedure
    - Test supervisor review for $500 procedure
    - Test supervisor review for $5000 procedure
    - Test human escalation for $5001 procedure
    - Test OAuth token refresh on expiration
    - Test edge case: $0 cost procedure
    - Test edge case: negative cost (invalid input)

- [x] 9. Integrate specialist agents with Orchestrator
  - Replace mock agents with real implementations
  - Test end-to-end orchestration flows for each request type
  - Verify error handling and escalation paths
  - _Requirements: 1.3, 1.4, 1.5_

- [x] 10. Checkpoint - Verify core specialist agents
  - Ensure all tests pass, ask the user if questions arise.

### Phase 3: Advanced Monitoring (Weeks 6-7)

- [ ] 11. Implement Adverse Event Monitor with AgentCore Memory
  - [ ] 11.1 Configure AgentCore Memory for episodic learning
    - Set up episodic memory storage with OpenSearch Serverless
    - Configure vector embeddings using amazon.titan-embed-text-v2
    - Set up 7-year retention policy with Glacier archival
    - Configure similarity search with 500ms latency target
    - _Requirements: 13.1, 13.3_
  
  - [ ] 11.2 Implement adverse event detection logic
    - Create AdverseEventCheckRequest and AdverseEventResponse data models
    - Implement symptom evaluation against known ADR patterns
    - Implement severity grade calculation (1-5 scale)
    - Generate immediate alerts for grade-3+ events
    - _Requirements: 3.1, 3.2, 3.4, 3.5_
  
  - [ ] 11.3 Implement episodic memory storage and retrieval
    - Store adverse event episodes with patient profile, symptoms, timeline, outcome
    - Generate vector embeddings for semantic similarity search
    - Retrieve top 10 similar historical cases within 500ms
    - Use retrieved cases to improve severity predictions
    - _Requirements: 3.3, 3.6, 3.7, 13.2, 13.4, 13.5_
  
  - [ ] 11.4 Implement pattern learning and feedback loop
    - Update pattern weights based on prediction accuracy
    - Implement daily pattern update frequency
    - Apply 0.8 confidence threshold for pattern application
    - _Requirements: 13.6_
  
  - [ ]* 11.5 Write property test for severity range
    - **Property 6: Adverse Event Severity Range**
    - **Validates: Requirements 3.4**
  
  - [ ]* 11.6 Write property test for high-severity alerts
    - **Property 7: High-Severity Alert Generation**
    - **Validates: Requirements 3.5**
  
  - [ ]* 11.7 Write property test for memory storage
    - **Property 8: Adverse Event Memory Storage**
    - **Validates: Requirements 13.2**
  
  - [ ]* 11.8 Write property test for historical case retrieval
    - **Property 9: Historical Case Retrieval**
    - **Validates: Requirements 13.4**
  
  - [ ]* 11.9 Write unit tests for Adverse Event Monitor
    - Test severity calculation for known patterns
    - Test alert generation for grade-3, grade-4, grade-5 events
    - Test episodic memory storage with all required fields
    - Test edge case: symptom with no matching patterns
    - Test edge case: empty medication list

- [ ] 12. Connect Patient Communication Agent escalation to Adverse Event Monitor
  - Implement escalation trigger in Patient Communication Agent
  - Pass concerning symptoms from Patient Communication to Adverse Event Monitor
  - Test end-to-end escalation flow
  - _Requirements: 6.6_

- [ ] 13. Test end-to-end adverse event detection and alerting
  - Test complete flow: symptom report → evaluation → memory retrieval → alert
  - Verify 500ms retrieval latency requirement
  - Test pattern learning feedback loop
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 14. Checkpoint - Verify adverse event monitoring
  - Ensure all tests pass, ask the user if questions arise.

### Phase 4: Interactive Communication (Weeks 8-9)

- [ ] 15. Implement Patient Communication Agent with BidiAgent pattern
  - [ ] 15.1 Set up bidirectional streaming infrastructure
    - Configure AgentCore Runtime for bidirectional streaming
    - Set up maximum 10 concurrent streams
    - Implement real-time audio streaming handlers
    - _Requirements: 6.2, 6.8, 16.1_
  
  - [ ] 15.2 Integrate Amazon Nova Sonic for speech processing
    - Configure Nova Sonic for speech-to-text conversion
    - Configure Nova Sonic for text-to-speech conversion
    - Implement real-time audio processing pipeline
    - _Requirements: 6.3, 16.2_
  
  - [ ] 15.3 Implement conversation flow and interruption handling
    - Create PatientCheckInRequest and PatientCheckInResponse data models
    - Implement standardized question flow (symptoms, medication, side effects)
    - Implement interruption detection and handling
    - Stop speaking when patient interrupts
    - Maintain conversation context across interruptions
    - Handle simultaneous speech by prioritizing patient input
    - _Requirements: 6.4, 6.5, 16.3, 16.4, 16.6_
  
  - [ ] 15.4 Implement conversation summary generation
    - Extract symptoms reported, medication adherence, concerns raised
    - Generate structured summary within 30 seconds
    - Include full transcript and audio recording URL
    - Trigger escalation flag for concerning symptoms
    - _Requirements: 6.6, 6.7_
  
  - [ ]* 15.5 Write property test for interruption handling
    - **Property 17: Patient Communication Interruption Handling**
    - **Validates: Requirements 6.4, 16.3**
  
  - [ ]* 15.6 Write property test for question coverage
    - **Property 18: Patient Communication Question Coverage**
    - **Validates: Requirements 6.5**
  
  - [ ]* 15.7 Write property test for escalation trigger
    - **Property 19: Patient Communication Escalation**
    - **Validates: Requirements 6.6**
  
  - [ ]* 15.8 Write property test for context preservation
    - **Property 20: Patient Communication Context Preservation**
    - **Validates: Requirements 16.4**
  
  - [ ]* 15.9 Write property test for input prioritization
    - **Property 21: Patient Communication Input Prioritization**
    - **Validates: Requirements 16.6**
  
  - [ ]* 15.10 Write unit tests for Patient Communication Agent
    - Test conversation flow with standardized questions
    - Test interruption handling and context preservation
    - Test escalation trigger for concerning symptoms
    - Test conversation summary generation
    - Test edge case: patient hangs up immediately
    - Test edge case: patient provides no verbal responses

- [ ] 16. Test bidirectional streaming and interruption handling
  - Test real-time speech processing with Nova Sonic
  - Verify <1 second response latency
  - Test multiple interruption scenarios
  - Test context preservation across conversation
  - _Requirements: 16.2, 16.3, 16.4, 16.5_

- [ ] 17. Validate conversation summary generation
  - Test summary generation within 30 seconds
  - Verify all required fields present (symptoms, adherence, concerns)
  - Test escalation to Adverse Event Monitor
  - _Requirements: 6.7, 6.6_

- [ ] 18. Checkpoint - Verify patient communication
  - Ensure all tests pass, ask the user if questions arise.

### Phase 5: Parallel Coordination (Weeks 10-12)

- [ ] 19. Implement Trial Coordinator Agent with Swarm Pattern
  - [ ] 19.1 Implement swarm spawning and management
    - Create TrialSchedulingRequest and TrialSchedulingResponse data models
    - Implement sub-agent spawning (one per patient)
    - Configure maximum concurrent sub-agents limit
    - Implement queuing for patients exceeding concurrency limit
    - Spawn next queued sub-agent when one completes
    - _Requirements: 7.1, 7.2, 20.1, 20.2, 20.3_
  
  - [ ] 19.2 Implement resource management and monitoring
    - Monitor resource usage across all sub-agents
    - Reduce concurrency when usage exceeds 80% capacity
    - Provide real-time progress updates (completed, in-progress, queued)
    - _Requirements: 20.4, 20.5, 20.6_
  
  - [ ]* 19.3 Write property test for sub-agent count
    - **Property 22: Trial Coordinator Sub-Agent Count**
    - **Validates: Requirements 7.2**
  
  - [ ]* 19.4 Write property test for queuing on concurrency limit
    - **Property 37: Trial Coordinator Queuing on Concurrency Limit**
    - **Validates: Requirements 20.2**
  
  - [ ]* 19.5 Write property test for queue processing
    - **Property 38: Trial Coordinator Queue Processing**
    - **Validates: Requirements 20.3**
  
  - [ ]* 19.6 Write property test for dynamic concurrency reduction
    - **Property 39: Trial Coordinator Dynamic Concurrency Reduction**
    - **Validates: Requirements 20.5**
  
  - [ ]* 19.7 Write property test for progress reporting
    - **Property 40: Trial Coordinator Progress Reporting**
    - **Validates: Requirements 20.6**

- [ ] 20. Develop A2A Protocol communication between sub-agents
  - [ ] 20.1 Implement A2A Protocol message handling
    - Create A2AMessage data model with all message types
    - Implement message sending with recipient specification
    - Implement broadcast messaging to all swarm agents
    - Guarantee message ordering for same sender-receiver pairs
    - Ensure 500ms message delivery latency
    - _Requirements: 7.3, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_
  
  - [ ] 20.2 Implement scheduling coordination logic
    - Implement time slot proposal broadcasting
    - Implement conflict detection between proposals
    - Implement negotiation protocol for alternative time slots
    - Consolidate all sub-agent results into unified schedule
    - Validate no resource conflicts in final schedule
    - _Requirements: 7.4, 7.5, 7.6, 7.7_
  
  - [ ]* 20.3 Write property test for proposal broadcasting
    - **Property 23: Trial Coordinator Proposal Broadcasting**
    - **Validates: Requirements 7.4**
  
  - [ ]* 20.4 Write property test for conflict negotiation
    - **Property 24: Trial Coordinator Conflict Negotiation**
    - **Validates: Requirements 7.5**
  
  - [ ]* 20.5 Write property test for result consolidation
    - **Property 25: Trial Coordinator Result Consolidation**
    - **Validates: Requirements 7.6**
  
  - [ ]* 20.6 Write property test for conflict-free schedule
    - **Property 26: Trial Coordinator Conflict-Free Schedule**
    - **Validates: Requirements 7.7**
  
  - [ ]* 20.7 Write property test for A2A message recipient specification
    - **Property 27: A2A Message Recipient Specification**
    - **Validates: Requirements 14.2**

- [ ] 21. Test multi-patient scheduling with conflict resolution
  - Test scheduling with 10 patients
  - Test scheduling with 100 patients (load test)
  - Verify conflict detection and resolution
  - Verify no double-booking in final schedules
  - Test concurrency limit enforcement
  - Test queuing and dynamic spawning
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 20.1, 20.2, 20.3_

- [ ]* 21.1 Write unit tests for Trial Coordinator Agent
  - Test sub-agent spawning for multiple patients
  - Test concurrency limit enforcement
  - Test queuing when limit exceeded
  - Test conflict detection in proposed schedules
  - Test conflict resolution through negotiation
  - Test final schedule consolidation
  - Test edge case: single patient (no coordination needed)
  - Test edge case: more patients than available time slots

- [ ] 22. Checkpoint - Verify parallel coordination
  - Ensure all tests pass, ask the user if questions arise.

### Phase 6: Integration and Hardening (Weeks 13-14)

- [ ] 23. End-to-end integration testing across all agents
  - Test complete patient screening workflow (Orchestrator → Patient Eligibility → Knowledge Base)
  - Test adverse event detection and alerting (Patient Communication → Adverse Event Monitor → Alert)
  - Test regulatory report generation (Orchestrator → Regulatory Report → Lambda → S3)
  - Test insurance authorization with external API (Orchestrator → Insurance Authorization → Identity → External API)
  - Test multi-patient scheduling (Orchestrator → Trial Coordinator → Sub-Agents → A2A)
  - _Requirements: All requirements_

- [ ] 24. Implement comprehensive error handling and recovery
  - [ ] 24.1 Implement retry with exponential backoff
    - Apply to transient errors (network, service unavailability, rate limiting)
    - Use formula: delay = 1 * (2 ^ attempt_number)
    - Maximum 3 retry attempts
    - _Requirements: 18.2_
  
  - [ ] 24.2 Implement checkpoint and resume functionality
    - Checkpoint agent state every 5 minutes
    - Store checkpoints with agent state, partial results, execution context
    - Implement resume from last checkpoint on failure
    - _Requirements: 11.3, 18.6_
  
  - [ ] 24.3 Implement graceful degradation
    - Preserve partial results from successful components
    - Mark incomplete sections in output
    - Continue execution with reduced functionality
    - _Requirements: 18.5_
  
  - [ ]* 24.4 Write property test for retry with exponential backoff
    - **Property 31: Orchestrator Retry with Exponential Backoff**
    - **Validates: Requirements 18.2, 18.3**
  
  - [ ]* 24.5 Write property test for API error messages
    - **Property 32: API Error Message Descriptiveness**
    - **Validates: Requirements 18.4**
  
  - [ ]* 24.6 Write property test for partial result preservation
    - **Property 33: Partial Result Preservation**
    - **Validates: Requirements 18.5**
  
  - [ ]* 24.7 Write property test for checkpoint-based recovery
    - **Property 34: Checkpoint-Based Recovery**
    - **Validates: Requirements 18.6**

- [ ] 25. Implement comprehensive audit logging
  - [ ] 25.1 Implement audit log capture
    - Log all coordination requests with timestamp and requester identity
    - Log all tool invocations with tool name, parameters, result
    - Log all policy evaluations with allow/deny outcomes
    - Log all authentication attempts and token usage
    - _Requirements: 19.1, 19.2, 19.3, 19.4_
  
  - [ ] 25.2 Implement audit log retention and export
    - Configure 7-year retention policy per FDA requirements
    - Implement JSON export format
    - Implement CSV export format
    - _Requirements: 19.5, 19.6_
  
  - [ ]* 25.3 Write property test for audit log completeness
    - **Property 35: Audit Log Completeness**
    - **Validates: Requirements 19.1, 19.2**
  
  - [ ]* 25.4 Write property test for audit log export formats
    - **Property 36: Audit Log Export Formats**
    - **Validates: Requirements 19.6**

- [ ] 26. Performance optimization and latency tuning
  - Optimize Adverse Event Monitor memory retrieval to <500ms
  - Optimize Patient Communication Agent response to <1s
  - Optimize policy evaluation to <100ms per tool call
  - Optimize PDF generation to <10s for 50-page reports
  - Test with 100 concurrent patients in Trial Coordinator
  - Test with 1000 historical episodes in Adverse Event Monitor
  - Test Orchestrator approaching 8-hour execution window
  - _Requirements: 3.7, 10.6, 15.3, 16.5_

- [ ] 27. Security audit and policy validation
  - Verify Cedar policies block unauthorized tool calls
  - Test policy evaluation for all cost thresholds
  - Verify OAuth token inclusion in all external API calls
  - Test token refresh on expiration
  - Verify patient identifiers not exposed in logs
  - Verify episodic memories use generalized patient profiles
  - Test data encryption at rest and in transit
  - _Requirements: 10.3, 10.4, 10.5, 10.6, 12.5, 12.6_

- [ ] 28. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at the end of each phase
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All code will be implemented in Python using AWS AgentCore Runtime and Strands framework
- The 6-phase approach manages complexity and enables early testing of each component
