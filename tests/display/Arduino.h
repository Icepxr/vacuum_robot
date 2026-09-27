#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
extern uint32_t displayTestNow;
inline uint32_t millis() { return displayTestNow; }
struct TestSerial { template<class... Args> void printf(const char*, Args...) {} };
inline TestSerial Serial;
