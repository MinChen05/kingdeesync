"""
加密工具模块
用于处理敏感信息的加密和解密
"""
import os
import sys
import base64
import uuid
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
try:
    import winreg  # Windows 注册表
except Exception:
    winreg = None

class CryptoUtil:
    """加密工具类"""

    # 遗留静态盐值，仅用于解密旧版本加密数据的回退兜底
    DEFAULT_SALT = b'kingdee_sync_salt_value'
    _CACHED_MACHINE_ID = None  # 缓存机器标识，避免重复查询
    _CACHED_SALT = None  # 缓存随机盐值

    @staticmethod
    def _get_salt_file_path() -> str:
        """返回盐值文件路径（与 config.ini 同目录）"""
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
            # 向上两级找项目根（src/utils/ -> src/ -> root/）
            root = os.path.dirname(os.path.dirname(exe_dir))
            candidate = os.path.join(root, '.install_salt')
            return candidate
        except Exception:
            return '.install_salt'

    @staticmethod
    def _get_or_create_salt() -> bytes:
        """获取或生成随机安装盐值，持久化到文件"""
        if CryptoUtil._CACHED_SALT is not None:
            return CryptoUtil._CACHED_SALT
        salt_path = CryptoUtil._get_salt_file_path()
        try:
            if os.path.exists(salt_path):
                with open(salt_path, 'rb') as f:
                    salt = f.read()
                if len(salt) >= 16:
                    CryptoUtil._CACHED_SALT = salt
                    return salt
        except Exception:
            pass
        # 生成新随机盐值并持久化
        salt = os.urandom(32)
        try:
            with open(salt_path, 'wb') as f:
                f.write(salt)
        except Exception:
            pass
        CryptoUtil._CACHED_SALT = salt
        return salt
    
    @staticmethod
    def generate_key(password: str, salt: bytes = None) -> bytes:
        """根据密码和盐值生成密钥"""
        if salt is None:
            salt = CryptoUtil.DEFAULT_SALT
            
        password_bytes = password.encode('utf-8')
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        return key
    
    @staticmethod
    def encrypt(text: str, key: bytes = None) -> str:
        """加密文本"""
        if not text:
            return ""
            
        if key is None:
            # 使用机器标识 + 随机安装盐值生成密钥
            machine_id = CryptoUtil._get_machine_id()
            salt = CryptoUtil._get_or_create_salt()
            key = CryptoUtil.generate_key(machine_id, salt)

        f = Fernet(key)
        encrypted_data = f.encrypt(text.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
    
    @staticmethod
    def decrypt(encrypted_text: str, key: bytes = None) -> str:
        """解密文本"""
        if not encrypted_text:
            return ""
            
        # 主密钥：机器标识 + 随机安装盐值
        if key is None:
            machine_id = CryptoUtil._get_machine_id()
            salt = CryptoUtil._get_or_create_salt()
            key = CryptoUtil.generate_key(machine_id, salt)

        # 1) 先用当前主密钥（随机盐）解密
        try:
            f = Fernet(key)
            decrypted_data = f.decrypt(base64.urlsafe_b64decode(encrypted_text))
            return decrypted_data.decode('utf-8')
        except Exception:
            pass

        # 2) 回退：用旧静态盐值解密（兼容升级前加密的数据）
        try:
            machine_id = CryptoUtil._get_machine_id()
            legacy_key = CryptoUtil.generate_key(machine_id, CryptoUtil.DEFAULT_SALT)
            f_legacy = Fernet(legacy_key)
            decrypted_data = f_legacy.decrypt(base64.urlsafe_b64decode(encrypted_text))
            return decrypted_data.decode('utf-8')
        except Exception:
            pass

        # 3) 兼容旧版本：尝试 wmic uuid 作为密码（Windows）
        if os.name == 'nt':
            try:
                import subprocess
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                CREATE_NO_WINDOW = 0x08000000
                result = subprocess.check_output(
                    ["wmic", "csproduct", "get", "uuid"],
                    startupinfo=startupinfo,
                    creationflags=CREATE_NO_WINDOW,
                    stderr=subprocess.STDOUT
                ).decode(errors="ignore")
                lines = [l.strip() for l in result.splitlines() if l.strip()]
                uuid_vals = [l for l in lines if l.lower() != "uuid"]
                if uuid_vals:
                    legacy_key = CryptoUtil.generate_key(uuid_vals[0])
                    f2 = Fernet(legacy_key)
                    decrypted_data = f2.decrypt(base64.urlsafe_b64decode(encrypted_text))
                    return decrypted_data.decode('utf-8')
            except Exception:
                pass
        # 解密失败则返回空字符串
        return ""
    
    @staticmethod
    def _get_machine_id() -> str:
        """获取机器唯一标识，用于生成密钥（Windows 优先使用注册表，避免命令窗口弹出）"""
        # 先返回缓存值，避免频繁查询导致性能问题或闪烁
        if CryptoUtil._CACHED_MACHINE_ID:
            return CryptoUtil._CACHED_MACHINE_ID

        # Windows 平台：优先读取注册表 MachineGuid，其次静默调用 wmic，最后回退 MAC 地址
        if os.name == 'nt':
            # 1) 优先从注册表读取，不会触发命令窗口
            if winreg is not None:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                        if isinstance(guid, str) and guid.strip():
                            CryptoUtil._CACHED_MACHINE_ID = guid.strip()
                            return CryptoUtil._CACHED_MACHINE_ID
                except Exception:
                    pass

            # 2) 回退到 wmic，但以不弹出窗口的方式调用
            try:
                import subprocess
                # 使用不显示窗口的方式启动子进程
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                CREATE_NO_WINDOW = 0x08000000
                result = subprocess.check_output(
                    ["wmic", "csproduct", "get", "uuid"],
                    startupinfo=startupinfo,
                    creationflags=CREATE_NO_WINDOW,
                    stderr=subprocess.STDOUT
                ).decode(errors="ignore")
                lines = [l.strip() for l in result.splitlines() if l.strip()]
                # 去掉表头行“UUID”，选择第一个非表头的值
                uuid_vals = [l for l in lines if l.lower() != "uuid"]
                if uuid_vals:
                    CryptoUtil._CACHED_MACHINE_ID = uuid_vals[0]
                    return CryptoUtil._CACHED_MACHINE_ID
            except Exception:
                pass

            # 3) 最后回退到 MAC 地址
            try:
                mac = uuid.getnode()
                CryptoUtil._CACHED_MACHINE_ID = str(mac)
                return CryptoUtil._CACHED_MACHINE_ID
            except Exception:
                pass

        # 非 Windows 平台：优先使用 /etc/machine-id
        try:
            with open('/etc/machine-id', 'r') as f:
                mid = f.read().strip()
                if mid:
                    CryptoUtil._CACHED_MACHINE_ID = mid
                    return CryptoUtil._CACHED_MACHINE_ID
        except Exception:
            pass

        # 最终回退：使用固定默认值
        CryptoUtil._CACHED_MACHINE_ID = "kingdee_sync_default_machine_id"
        return CryptoUtil._CACHED_MACHINE_ID
