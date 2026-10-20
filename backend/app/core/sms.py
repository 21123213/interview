"""短信认证服务模块 - 阿里云 PNVS 短信认证服务"""
import os
from typing import Optional, Dict
from alibabacloud_dypnsapi20170525.client import Client as Dypnsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dypnsapi20170525 import models as dypnsapi_20170525_models
from alibabacloud_tea_util import models as util_models


class PNVSService:
    """阿里云 PNVS 短信认证服务
    
    特点：
    - 无需企业资质，个人账号可用
    - 无需签名和模板审核，使用预置资源
    - 验证码由系统生成或自定义
    - 验证码校验由阿里云托管
    """
    
    def __init__(self):
        # 从环境变量获取配置
        access_key_id = os.getenv('ALIYUN_ACCESS_KEY_ID')
        access_key_secret = os.getenv('ALIYUN_ACCESS_KEY_SECRET')
        self.sign_name = os.getenv('ALIYUN_SMS_SIGN_NAME', '阿里云')
        self.template_code = os.getenv('ALIYUN_SMS_TEMPLATE_CODE')
        
        # 读取调试模式（增强调试）
        debug_env = os.getenv('APP_DEBUG', 'False')
        print(f"🔍 环境变量 APP_DEBUG 原始值: '{debug_env}'")
        self.debug_mode = debug_env.lower() in ['true', '1', 'yes']
        print(f"🔍 解析后 debug_mode: {self.debug_mode}")
        
        # 验证必要配置
        if not all([access_key_id, access_key_secret, self.template_code]):
            raise ValueError("缺少必要的阿里云配置：ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET, ALIYUN_SMS_TEMPLATE_CODE")
        
        # 创建客户端配置（使用 AccessKey 方式）
        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret
        )
        # Endpoint 参考: https://api.aliyun.com/product/Dypnsapi
        config.endpoint = f'dypnsapi.aliyuncs.com'
        
        self.client = Dypnsapi20170525Client(config)
        
        print(f"✅ PNVS服务初始化成功")
        print(f"   - 签名: {self.sign_name}")
        print(f"   - 模板: {self.template_code}")
        print(f"   - 调试模式: {self.debug_mode}")
    
    def send_verification_code(
        self, 
        phone: str,
        custom_code: Optional[str] = None,
        valid_time: int = 5,
        out_id: Optional[str] = None
    ) -> Dict[str, any]:
        """
        发送验证码短信
        
        :param phone: 手机号（11位，中国大陆）
        :param custom_code: 自定义验证码（4-6位数字），None则由系统生成
        :param valid_time: 验证码有效期（分钟），默认5分钟
        :param out_id: 外部流水号，用于幂等性控制
        :return: {
            'success': bool,
            'code': str,  # 验证码（仅测试模式返回）
            'biz_id': str,  # 业务ID
            'message': str,
            'out_id': str  # 外部流水号
        }
        """
        # 调试模式：不发送真实短信
        if self.debug_mode:
            test_code = custom_code or '123456'
            print(f"🧪 [测试模式] 手机号: {phone}, 验证码: {test_code}")
            return {
                'success': True,
                'code': test_code,
                'biz_id': 'TEST_BIZ_ID',
                'message': '测试模式，未发送真实短信',
                'out_id': out_id or ''
            }
        
        try:
            print(f"📱 准备发送验证码到: {phone}")
            print(f"   - 签名: {self.sign_name}")
            print(f"   - 模板: {self.template_code}")
            if custom_code:
                print(f"   - 自定义验证码: {custom_code}")
            
            # 构造模板参数
            if custom_code:
                # 使用自定义验证码
                template_param = f'{{"code":"{custom_code}","min":"5"}}'
            else:
                # 使用系统生成验证码（##code## 占位符）
                template_param = '{"code":"##code##","min":"5"}'
            
            # 构造请求（参考官方示例）
            send_sms_verify_code_request = dypnsapi_20170525_models.SendSmsVerifyCodeRequest(
                phone_number=phone,
                sign_name=self.sign_name,
                template_code=self.template_code,
                template_param=template_param,
                valid_time=valid_time * 60,  # 有效期（秒）
                out_id=out_id,  # 外部流水号
                code_type=1,  # 1=数字验证码
                code_length=6,  # 验证码长度
                return_verify_code=False,  # 生产环境不返回验证码
                duplicate_policy=1,  # 1=覆盖旧验证码
                interval=60  # 60秒内不允许重复发送
            )
            
            runtime = util_models.RuntimeOptions()
            
            # 调用发送接口
            response = self.client.send_sms_verify_code_with_options(
                send_sms_verify_code_request, 
                runtime
            )
            
            print(f"📤 PNVS响应: Code={response.body.code}, Message={response.body.message}")
            
            # 检查响应
            if response.body.code == 'OK':
                # 根据 API 文档，业务数据在 model 字段中
                model = response.body.model if hasattr(response.body, 'model') else None
                
                return {
                    'success': True,
                    'code': None,  # 生产环境不返回验证码
                    'biz_id': model.biz_id if model and hasattr(model, 'biz_id') else 'N/A',
                    'message': '验证码发送成功',
                    'out_id': model.out_id if model and hasattr(model, 'out_id') else (out_id or '')
                }
            else:
                return {
                    'success': False,
                    'code': None,
                    'biz_id': None,
                    'message': f"发送失败: {response.body.message}",
                    'out_id': out_id or ''
                }
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ PNVS发送异常: {error_msg}")
            return {
                'success': False,
                'code': None,
                'biz_id': None,
                'message': f"发送异常: {error_msg}",
                'out_id': out_id or ''
            }
    
    def verify_code(
        self, 
        phone: str, 
        code: str,
        out_id: Optional[str] = None
    ) -> Dict[str, any]:
        """
        验证验证码（阿里云托管校验）
        
        :param phone: 手机号
        :param code: 用户输入的验证码
        :param out_id: 发送时的外部流水号
        :return: {
            'success': bool,
            'message': str
        }
        """
        # 调试模式：固定验证码
        if self.debug_mode:
            is_valid = (code == '123456')
            print(f"🧪 [测试模式] 验证码校验: {phone} -> {code} -> {'通过' if is_valid else '失败'}")
            return {
                'success': is_valid,
                'message': '验证码正确' if is_valid else '验证码错误'
            }
        
        try:
            print(f"🔍 验证码校验: {phone} -> {code}")
            
            # 参考官方示例构造请求
            check_sms_verify_code_request = dypnsapi_20170525_models.CheckSmsVerifyCodeRequest()
            check_sms_verify_code_request.phone_number = phone
            check_sms_verify_code_request.verify_code = code
            if out_id:
                check_sms_verify_code_request.out_id = out_id
            check_sms_verify_code_request.case_auth_policy = 1  # 1=不区分大小写
            
            runtime = util_models.RuntimeOptions()
            
            # 调用验证接口（参考官方示例）
            response = self.client.check_sms_verify_code_with_options(
                check_sms_verify_code_request, 
                runtime
            )
            
            print(f"✔️ 校验响应: Code={response.body.code}, Message={response.body.message}")
            
            # 检查响应（参考官方文档）
            if response.body.code == 'OK':
                # 根据 API 文档，验证结果在 model.verify_result 中
                model = response.body.model if hasattr(response.body, 'model') else None
                
                if model and hasattr(model, 'verify_result'):
                    verify_result = model.verify_result
                    print(f"   验证结果: {verify_result}")
                    
                    if verify_result == 'PASS':
                        return {
                            'success': True,
                            'message': '验证码正确'
                        }
                    else:
                        return {
                            'success': False,
                            'message': '验证码错误或已过期'
                        }
                else:
                    # 如果没有 model.verify_result，认为验证成功
                    return {
                        'success': True,
                        'message': '验证码正确'
                    }
            else:
                return {
                    'success': False,
                    'message': f"验证失败: {response.body.message}"
                }
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 验证异常: {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f"验证异常: {error_msg}"
            }


# 全局 PNVS 服务实例
try:
    pnvs_service = PNVSService()
except Exception as e:
    print(f"⚠️ PNVS服务初始化失败: {e}")
    pnvs_service = None


def send_sms_code(phone: str, out_id: Optional[str] = None) -> Optional[str]:
    """
    发送短信验证码的便捷函数（兼容旧接口）
    
    :param phone: 手机号
    :param out_id: 外部流水号（可选）
    :return: 验证码（测试模式）或 'SENT'（生产模式），失败返回 None
    """
    if not pnvs_service:
        print("❌ PNVS服务未初始化")
        return None
    
    result = pnvs_service.send_verification_code(phone, out_id=out_id)
    
    if result['success']:
        # 测试模式返回验证码，生产模式返回标识
        return result.get('code') or 'SENT'
    else:
        return None
