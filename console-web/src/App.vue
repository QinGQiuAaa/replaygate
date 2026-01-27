<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand">ReplayGate Console</div>
      <div class="nav">
        <el-button type="primary" plain @click="$router.push('/')">任务列表</el-button>
        <el-button type="success" plain @click="$router.push('/runs/new')">创建任务</el-button>
      </div>
    </el-header>
    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: linear-gradient(135deg, #f6f3ee 0%, #f1f7ff 100%);
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #111827;
  color: #fff;
  padding: 0 24px;
}
.brand {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.nav {
  display: flex;
  gap: 12px;
}
.main {
  padding: 24px;
}
</style>
