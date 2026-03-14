#!/usr/bin/env python3
"""
Skill 配置检索器
扫描本地所有 skills，检测需要配置的 API keys、tokens、secrets 等
"""

import os
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class ConfigRequirement:
    """配置需求"""
    skill_name: str
    config_type: str  # api_key, oauth, env_var, credential
    config_key: str   # 例如: OPENAI_API_KEY
    description: str
    how_to_get: str
    config_steps: str
    skill_path: str
    agent: str = "未知"

class SkillConfigChecker:
    def __init__(self):
        self.skills_dirs = [
            Path.home() / ".openclaw" / "skills",
            Path.home() / "clawd" / "skills"
        ]
        self.pass_store_path = Path.home() / ".password-store" / "api"
        self.config_patterns = {
            "api_key": [
                r'API[_\-]?KEY["\']?\s*[:=]',
                r'api[_\-]?key["\']?\s*[:=]',
                r'API\s+key',
            ],
            "env_var": [
                r'export\s+([A-Z_][A-Z0-9_]*)=',
                r'([A-Z_][A-Z0-9_]*)\s*环境变量',
                r'\$([A-Z_][A-Z0-9_]*)',
            ],
            "oauth": [
                r'OAuth',
                r'oauth',
                r'授权链接',
                r'Rube\s+MCP',
            ],
            "credential": [
                r'app[_\-]?id',
                r'app[_\-]?secret',
                r'client[_\-]?id',
                r'client[_\-]?secret',
                r'credential',
            ],
            "pass_store": [
                r'pass\s+show\s+api/([a-z0-9\-_]+)',
            ]
        }
        self.known_services = {
            "OPENAI_API_KEY": {
                "service": "OpenAI",
                "how_to_get": "https://platform.openai.com/api-keys",
                "config_steps": "export OPENAI_API_KEY='your-key'"
            },
            "GEMINI_API_KEY": {
                "service": "Google AI Studio",
                "how_to_get": "https://aistudio.google.com/",
                "config_steps": "export GEMINI_API_KEY='your-key'"
            },
            "ANTHROPIC_API_KEY": {
                "service": "Anthropic",
                "how_to_get": "https://console.anthropic.com/",
                "config_steps": "export ANTHROPIC_API_KEY='your-key'"
            },
            "TWITTER_API_KEY": {
                "service": "Twitter Developer",
                "how_to_get": "https://developer.twitter.com/",
                "config_steps": "export TWITTER_API_KEY='your-key'"
            },
            "MODELSCOPE_API_KEY": {
                "service": "ModelScope",
                "how_to_get": "https://modelscope.cn/",
                "config_steps": "export MODELSCOPE_API_KEY='your-key'"
            },
        }
        self.agents_skills = self._load_agents_skills()
    
    def _load_agents_skills(self) -> Dict[str, List[str]]:
        """加载各个 agent 已配置的 skills"""
        agents_dir = Path.home() / ".openclaw" / "agents"
        agents_skills = {}
        
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    agent_json = agent_dir / "agent" / "agent.json"
                    if agent_json.exists():
                        try:
                            import json
                            with open(agent_json) as f:
                                data = json.load(f)
                                agents_skills[agent_dir.name] = data.get("skills", [])
                        except:
                            pass
        
        return agents_skills
    
    def _get_skill_agent(self, skill_name: str) -> str:
        """获取 skill 所属的 agent"""
        for agent, skills in self.agents_skills.items():
            if skill_name in skills:
                return agent
        return "未分配"
    
    def _check_pass_store(self, service: str) -> bool:
        """检查 pass store 中是否有该服务的配置"""
        pass_file = self.pass_store_path / f"{service}.gpg"
        return pass_file.exists()
    
    def _extract_config_requirements(self, skill_md_path: Path) -> List[ConfigRequirement]:
        """从 SKILL.md 文件中提取配置需求"""
        requirements = []
        
        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return requirements
        
        skill_name = skill_md_path.parent.name
        agent = self._get_skill_agent(skill_name)
        
        # 检查是否有 "无需配置" 的标记
        if re.search(r'无需.*配置|不需要.*API.*key|No API keys required', content, re.IGNORECASE):
            return requirements
        
        # 检查 API keys
        for pattern in self.config_patterns["api_key"]:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # 尝试提取变量名
                var_match = re.search(r'([A-Z_][A-Z0-9_]*)', match.group(0))
                if var_match:
                    var_name = var_match.group(1)
                    service_info = self.known_services.get(var_name, {
                        "service": "Unknown",
                        "how_to_get": "查看 SKILL.md 文件",
                        "config_steps": f"export {var_name}='your-key'"
                    })
                    
                    # 检查是否已在 pass store 中
                    service_key = var_name.lower().replace('_api_key', '').replace('_', '-')
                    is_configured = self._check_pass_store(service_key)
                    
                    requirements.append(ConfigRequirement(
                        skill_name=skill_name,
                        config_type="已配置" if is_configured else "api_key",
                        config_key=var_name,
                        description=f"{service_info['service']} API Key",
                        how_to_get=service_info['how_to_get'],
                        config_steps=service_info['config_steps'],
                        skill_path=str(skill_md_path.parent),
                        agent=agent
                    ))
        
        # 检查环境变量
        for pattern in self.config_patterns["env_var"]:
            matches = re.finditer(pattern, content)
            for match in matches:
                var_name = match.group(1) if match.lastindex else match.group(0)
                if var_name and var_name not in [r.config_key for r in requirements]:
                    service_info = self.known_services.get(var_name, {
                        "service": "Unknown",
                        "how_to_get": "查看 SKILL.md 文件",
                        "config_steps": f"export {var_name}='your-key'"
                    })
                    
                    requirements.append(ConfigRequirement(
                        skill_name=skill_name,
                        config_type="env_var",
                        config_key=var_name,
                        description=f"{service_info['service']} 环境变量",
                        how_to_get=service_info['how_to_get'],
                        config_steps=service_info['config_steps'],
                        skill_path=str(skill_md_path.parent),
                        agent=agent
                    ))
        
        # 检查 OAuth
        if re.search('|'.join(self.config_patterns["oauth"]), content, re.IGNORECASE):
            requirements.append(ConfigRequirement(
                skill_name=skill_name,
                config_type="oauth",
                config_key="OAuth",
                description="OAuth 授权",
                how_to_get="我会提供授权链接",
                config_steps="点击授权链接完成授权",
                skill_path=str(skill_md_path.parent),
                agent=agent
            ))
        
        # 检查 pass store
        for pattern in self.config_patterns["pass_store"]:
            matches = re.finditer(pattern, content)
            for match in matches:
                service = match.group(1)
                is_configured = self._check_pass_store(service)
                
                requirements.append(ConfigRequirement(
                    skill_name=skill_name,
                    config_type="已配置" if is_configured else "pass_store",
                    config_key=f"api/{service}",
                    description=f"Pass store: api/{service}",
                    how_to_get="pass insert api/{}".format(service),
                    config_steps=f"pass insert api/{service}",
                    skill_path=str(skill_md_path.parent),
                    agent=agent
                ))
        
        return requirements
    
    def scan_all_skills(self) -> List[ConfigRequirement]:
        """扫描所有 skills"""
        all_requirements = []
        scanned_skills = set()
        
        for skills_dir in self.skills_dirs:
            if not skills_dir.exists():
                continue
            
            for skill_path in skills_dir.rglob("SKILL.md"):
                skill_name = skill_path.parent.name
                
                # 避免重复扫描
                if skill_name in scanned_skills:
                    continue
                scanned_skills.add(skill_name)
                
                requirements = self._extract_config_requirements(skill_path)
                all_requirements.extend(requirements)
        
        return all_requirements
    
    def generate_report(self, requirements: List[ConfigRequirement], verbose: bool = False) -> str:
        """生成配置报告"""
        # 按配置类型分组
        configured = [r for r in requirements if r.config_type == "已配置"]
        need_config = [r for r in requirements if r.config_type in ["api_key", "env_var", "pass_store"]]
        need_oauth = [r for r in requirements if r.config_type == "oauth"]
        
        # 去重
        need_config_unique = list({r.config_key: r for r in need_config}.values())
        need_oauth_unique = list({r.skill_name: r for r in need_oauth}.values())
        
        report = []
        report.append("📋 Skills 配置需求总览\n")
        report.append("=" * 60)
        
        # 已配置的 Skills
        if configured:
            report.append(f"\n✅ 已配置的 Skills ({len(configured)})")
            for req in configured[:10]:  # 只显示前10个
                report.append(f"  - {req.skill_name} ({req.agent})")
                if verbose:
                    report.append(f"    配置: {req.config_key}")
        
        # 需要配置的 Skills
        if need_config_unique:
            report.append(f"\n⚠️ 需要配置的 Skills ({len(need_config_unique)})")
            for i, req in enumerate(need_config_unique, 1):
                report.append(f"\n  {i}. {req.skill_name} ({req.agent})")
                report.append(f"     - 需要: {req.config_key}")
                report.append(f"     - 获取: {req.how_to_get}")
                report.append(f"     - 配置: {req.config_steps}")
        
        # 需要 OAuth 授权的 Skills
        if need_oauth_unique:
            report.append(f"\n🔐 需要 OAuth 授权的 Skills ({len(need_oauth_unique)})")
            for req in need_oauth_unique:
                report.append(f"  - {req.skill_name} ({req.agent})")
                report.append(f"    授权: {req.how_to_get}")
        
        # 操作建议
        if need_config_unique or need_oauth_unique:
            report.append("\n📝 立即行动清单")
            report.append("-" * 60)
            
            for i, req in enumerate(need_config_unique[:5], 1):
                report.append(f"\n{i}. 配置 {req.config_key}")
                report.append(f"   获取地址: {req.how_to_get}")
                report.append(f"   执行命令: {req.config_steps}")
            
            if need_oauth_unique:
                report.append(f"\n{len(need_config_unique)+1}. OAuth 授权")
                report.append("   我会为你生成授权链接，点击即可完成授权")
        
        report.append("\n" + "=" * 60)
        report.append(f"\n总计: {len(requirements)} 个配置项")
        report.append(f"  - 已配置: {len(configured)}")
        report.append(f"  - 待配置: {len(need_config_unique)}")
        report.append(f"  - OAuth: {len(need_oauth_unique)}")
        
        return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description="Skill 配置检索器")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    parser.add_argument("--agent", "-a", type=str, help="只检查特定 agent 的 skills")
    parser.add_argument("--output", "-o", type=str, help="输出到文件")
    args = parser.parse_args()
    
    checker = SkillConfigChecker()
    requirements = checker.scan_all_skills()
    
    # 过滤特定 agent
    if args.agent:
        requirements = [r for r in requirements if args.agent.lower() in r.agent.lower()]
    
    report = checker.generate_report(requirements, args.verbose)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告已保存到: {args.output}")
    else:
        print(report)

if __name__ == "__main__":
    main()
