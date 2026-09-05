#include "encoder.h"

bool IRAM_ATTR QuadEncoder::onReach(pcnt_unit_handle_t unit,
                                    const pcnt_watch_event_data_t* edata,
                                    void* ctx) {
  auto* self = static_cast<QuadEncoder*>(ctx);
  // ฮาร์ดแวร์รีเซ็ตตัวนับกลับเป็น 0 เองเมื่อชน limit → สะสมค่าที่ชนเข้าตัวแปร 64 บิต
  portENTER_CRITICAL_ISR(&self->mux_);
  self->accum_ += edata->watch_point_value;
  self->wraps_++;
  portEXIT_CRITICAL_ISR(&self->mux_);
  return false;  // ไม่ต้องปลุก task ระดับสูงกว่า
}

bool QuadEncoder::begin(int pinA, int pinB, bool invert) {
  invert_ = invert;

  pcnt_unit_config_t unit_cfg = {};
  unit_cfg.low_limit = -PCNT_LIMIT;
  unit_cfg.high_limit = PCNT_LIMIT;
  if (pcnt_new_unit(&unit_cfg, &unit_) != ESP_OK) return false;

  // กรอง glitch 1 µs — ที่ความเร็วเต็ม ขอบสัญญาณห่างกัน ~137 µs (1/7310)
  // จึงกรองได้สบายโดยไม่กินสัญญาณจริง
  pcnt_glitch_filter_config_t filt = {};
  filt.max_glitch_ns = 1000;
  if (pcnt_unit_set_glitch_filter(unit_, &filt) != ESP_OK) return false;

  pcnt_channel_handle_t chA = nullptr, chB = nullptr;

  pcnt_chan_config_t cfgA = {};
  cfgA.edge_gpio_num = pinA;
  cfgA.level_gpio_num = pinB;
  if (pcnt_new_channel(unit_, &cfgA, &chA) != ESP_OK) return false;

  pcnt_chan_config_t cfgB = {};
  cfgB.edge_gpio_num = pinB;
  cfgB.level_gpio_num = pinA;
  if (pcnt_new_channel(unit_, &cfgB, &chB) != ESP_OK) return false;

  const auto up = PCNT_CHANNEL_EDGE_ACTION_INCREASE;
  const auto dn = PCNT_CHANNEL_EDGE_ACTION_DECREASE;
  pcnt_channel_set_edge_action(chA, invert_ ? up : dn, invert_ ? dn : up);
  pcnt_channel_set_level_action(chA, PCNT_CHANNEL_LEVEL_ACTION_KEEP,
                                PCNT_CHANNEL_LEVEL_ACTION_INVERSE);
  pcnt_channel_set_edge_action(chB, invert_ ? dn : up, invert_ ? up : dn);
  pcnt_channel_set_level_action(chB, PCNT_CHANNEL_LEVEL_ACTION_KEEP,
                                PCNT_CHANNEL_LEVEL_ACTION_INVERSE);

  // กันล้น: §1.5 ตั้ง watch point ที่ ±30,000 แล้วสะสมเองใน callback
  pcnt_unit_add_watch_point(unit_, PCNT_LIMIT);
  pcnt_unit_add_watch_point(unit_, -PCNT_LIMIT);
  pcnt_event_callbacks_t cbs = {};
  cbs.on_reach = QuadEncoder::onReach;
  if (pcnt_unit_register_event_callbacks(unit_, &cbs, this) != ESP_OK) return false;

  // Hall ของมอเตอร์ตระกูลนี้บางล็อตเป็น open-drain → เปิด pull-up ภายในไว้
  // (ถ้าเป็น push-pull อยู่แล้ว การเปิด pull-up ไม่ทำอันตราย)
  gpio_set_pull_mode(static_cast<gpio_num_t>(pinA), GPIO_PULLUP_ONLY);
  gpio_set_pull_mode(static_cast<gpio_num_t>(pinB), GPIO_PULLUP_ONLY);

  if (pcnt_unit_enable(unit_) != ESP_OK) return false;
  if (pcnt_unit_clear_count(unit_) != ESP_OK) return false;
  if (pcnt_unit_start(unit_) != ESP_OK) return false;
  return true;
}

int64_t QuadEncoder::count() {
  // accum_ เป็น 64 บิตบนชิป 32 บิต → การอ่านไม่ใช่ atomic
  // ถ้า callback ของ watch point แทรกกลางระหว่างอ่าน จะได้ค่าครึ่งเก่าครึ่งใหม่
  // จึงต้องกันด้วย critical section (callback ทำงานใน ISR context)
  int raw = 0;
  int64_t acc = 0;
  portENTER_CRITICAL(&mux_);
  acc = accum_;
  portEXIT_CRITICAL(&mux_);
  pcnt_unit_get_count(unit_, &raw);
  return acc + raw;
}

void QuadEncoder::zero() {
  pcnt_unit_stop(unit_);
  pcnt_unit_clear_count(unit_);
  portENTER_CRITICAL(&mux_);
  accum_ = 0;
  wraps_ = 0;
  portEXIT_CRITICAL(&mux_);
  pcnt_unit_start(unit_);
}
