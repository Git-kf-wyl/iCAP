<template>
  <div class="device-card" @click="handleClick">
    <div class="device-icon" :class="`status-${device.status}`">
      # {{ device['手机编号'] }}
    </div>
    <div class="device-detail">
      <div>
        <strong>序列号</strong>
        <span>{{ device.id || '—' }}</span>
      </div>
      <div>
        <strong>资产编号</strong>
        <span>{{ device.asset || '—' }}</span>
      </div>
      <div>
        <strong>手机型号</strong>
        <span>{{ device.product_model || '—' }}</span>
      </div>
      <div>
        <strong>当前APP</strong>
        <span>{{ device.current_app || '—' }}</span>
      </div>
      <div>
        <strong>电量</strong>
        <span>{{ device.battery || '—' }}</span>
      </div>
      <div>
        <strong>状态</strong>
        <span 
          class="status-text" 
          :data-status="device.status"
        >
          {{ getStatusText(device.status) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DeviceCard',
  props: {
    device: {
      type: Object,
      required: true
    }
  },
  emits: ['click'],
  methods: {
    getStatusText(status) {
      const statusMap = {
        0: '空闲',
        1: '采集中',
        2: '异常'
      }
      return statusMap[status] || '未知'
    },
    handleClick() {
      console.log('DeviceCard被点击，设备ID:', this.device['手机编号'])
      this.$emit('click', this.device['手机编号'])
    }
  }
}
</script>

<style scoped>
.device-card {
  background: white;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  gap: 15px;
}

.device-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.device-icon {
  background: #f0f0f0;
  border-radius: 8px;
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
}

.device-icon.status-0 {
  background: #2ecc71;
  color: white;
}

.device-icon.status-1 {
  background: #3498db;
  color: white;
}

.device-icon.status-2 {
  background: #e74c3c;
  color: white;
}

.device-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.device-detail div {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.device-detail strong {
  color: #333;
  font-size: 14px;
}

.device-detail span {
  color: #666;
  font-size: 14px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-text {
  font-weight: bold;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.status-text[data-status="0"] {
  background: #d5f4e6;
  color: #27ae60;
}

.status-text[data-status="1"] {
  background: #d6eaff;
  color: #2980b9;
}

.status-text[data-status="2"] {
  background: #fadbd8;
  color: #e74c3c;
}
</style>