# 远程部署方案指南 (Remote Deployment)

此项目生成的 Token 属于 **Public Client (桌面/脚本)** 类型。
**核心铁律**：Azure AD 规定，Public Client 的回调地址（Redirect URI）**只能**是 `http://localhost`。不能配置为 `http://your-server.com`，除非你把它改成 Confidential Client（但这会导致生成的 Token 需要密码才能刷新，破坏自动化脚本）。

因此，在远程服务器（VPS/云主机）上运行时，我们有以下两种标准方案：

---

## 方案 A：SSH 隧道 (推荐，零代码修改)
**原理**：把你本地电脑的 5000 端口，通过 SSH "打洞" 连接到服务器的 5000 端口。
**优点**：
1. Azure 配置完全不用改（保持 `http://localhost`）。
2. 代码完全不用改。
3. 数据最安全（通过加密通道传输）。

**操作步骤**：

1. **在服务器上启动应用**：
   ```bash
   # 在服务器终端运行
   python main.py
   # 确保它监听 0.0.0.0 或者 127.0.0.1 都可以，最好是 127.0.0.1 以防外网直接扫到
   ```

2. **在本地电脑建立隧道**：
   打开你的本地 CMD 或终端，运行：
   ```bash
   # 格式：ssh -L 本地端口:127.0.0.1:远程端口 用户@服务器IP
   ssh -L 5000:127.0.0.1:5000 root@your-server-ip
   ```
   *输入密码登录成功后，保持这个窗口打开不要关。*

3. **本地浏览器访问**：
   直接在**你自己的电脑**浏览器打开：
   `http://localhost:5000`

   **结果**：你看到的页面虽然是本地的 `localhost`，但实际流量已经穿透到了服务器，生成的 Token 会直接保存在服务器的 `accounts.json` 里。

---

## 方案 C：Docker 部署 (配合 SSH 隧道)
**当然可以部署到 Docker！** 原理是一样的。
Docker 只是改变了运行环境，没有改变 OAuth 协议的规则（必须是 localhost）。

**1. 准备配置文件（关键！）**
由于 Docker 挂载机制的特性，如果宿主机上文件不存在，Docker 会自动创建一个**文件夹**而不是文件，这会导致报错 `Are you trying to mount a directory onto a file?`。

因此，**在启动之前**，请务必在服务器目录 (`/opt/1panel/...`) 执行以下命令：
```bash
# 1. 创建空的 json 文件 (防止被识别为目录)
echo "{}" > accounts.json

# 2. 准备 .env 文件
# 确保包含 NOTIFY_API_URL 等新变量
cp .env.example .env
vi .env
```

**2. 启动 Docker 容器：**
我们现在使用 Python 调度器管理服务：
```bash
docker-compose up -d --build
```
查看日志：
```bash
# -f 参数很重要，因为使用了 python -u，日志是实时的
docker-compose logs -f
```

**2. 依然需要 "SSH 打洞"：**
因为你不能直接访问远程 `http://your-server-ip:5000` (Azure 会拒绝，因为它只认 `localhost`)。
**你还是需要照搬方案 A 的第 2 步**：

在本地电脑运行：
```bash
ssh -L 5000:127.0.0.1:5000 root@your-server-ip
```

**3. 访问流程：**
[你本地浏览器] -> `http://localhost:5000` -> [SSH 隧道] -> [服务器 5000 端口] -> [Docker 容器 5000 端口] -> [Flask 应用]

**好处**：
- 环境隔离，不用操心 Python 版本。
- `accounts.json` 通过 Volume 映射出来，数据安全。
- 以后要迁移服务器，直接把文件夹拷走，docker-compose up 即可。

---

## 方案 B：设备代码流 (Device Code Flow)
**原理**：不显示网页，而是在终端打印一个代码（如 `A1B2C3D4`），你去 microsoft.com/devicelogin 输入这个代码。
**适用场景**：你没有 SSH 权限，或者网络极度受限。
**缺点**：**需要修改代码**，把网页版逻辑改成命令行交互逻辑。

**如果你需要方案 B，请告诉我，我为你重写一个 `manual_login.py` 脚本。**

---

## 💡 总结
**绝大多数情况下，请使用方案 A。**
它是最符合 Linus 哲学的方案：利用现有的工具（SSH）解决问题，而不是引入新的复杂性。
