#include "Inkplate.h"
#include "WiFi.h"
#include "secrets.h"

constexpr uint64_t US_PER_SECOND = 1000000ULL;
constexpr uint64_t NORMAL_SLEEP_SECONDS = 24ULL * 60ULL * 60ULL;
constexpr uint64_t RETRY_SLEEP_SECONDS = 15ULL * 60ULL;

RTC_DATA_ATTR bool hasRenderedBriefing = false;

Inkplate display(INKPLATE_3BIT);

void sleepFor(uint64_t seconds)
{
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    esp_sleep_enable_timer_wakeup(seconds * US_PER_SECOND);
    esp_deep_sleep_start();
}

void showInitialError(const char *message)
{
    if (hasRenderedBriefing)
        return;

    display.clearDisplay();
    display.setTextColor(BLACK);
    display.setTextSize(2);
    display.setCursor(24, 40);
    display.println("Morning Desk");
    display.setTextSize(1);
    display.setCursor(24, 80);
    display.println(message);
    display.display();
}

void setup()
{
    Serial.begin(115200);
    display.begin();

    if (!display.connectWiFi(WIFI_SSID, WIFI_PASSWORD, 20000, true))
    {
        showInitialError("Wi-Fi unavailable. Retrying in 15 minutes.");
        sleepFor(RETRY_SLEEP_SECONDS);
    }

    display.clearDisplay();
    bool rendered = display.image.drawPngFromWeb(
        BRIEFING_URL,
        0,
        0,
        false,
        false
    );

    if (!rendered)
    {
        showInitialError("Briefing unavailable. Retrying in 15 minutes.");
        sleepFor(RETRY_SLEEP_SECONDS);
    }

    display.display();
    hasRenderedBriefing = true;
    sleepFor(NORMAL_SLEEP_SECONDS);
}

void loop()
{
}
