# MINISTÉRIO DA EDUCAÇÃO
**UNIVERSIDADE FEDERAL DO AGRESTE DE PERNAMBUCO**  
**BACHARELADO EM CIÊNCIA DA COMPUTAÇÃO**

## PROJETO PRÁTICO DA DISCIPLINA
* **Disciplina:** Sistemas de informação e tecnologias
* **Professor:** Dr. Assuero Fonseca Ximenes
* **Período:** 2026.2

---

## 1. OBJETIVO GERAL

Desenvolver, de forma prática e integrada, partes essenciais de um Sistema de gestão, contemplando:

* a camada operacional, por meio da implementação de módulos de um sistema transacional (ERP simplificado), responsáveis pela entrada, processamento, armazenamento de dados e saídas;
* a camada de análise, por meio da construção de dashboards (Business Intelligence), responsáveis pela análise, visualização e apoio à tomada de decisão.

O objetivo da disciplina não é desenvolver um sistema completo, mas sim simular, em escala reduzida, o funcionamento de um Sistema de Informação real, permitindo que os estudantes:

* Compreendam como os dados são gerados nos processos operacionais;
* Implementem módulos integrados que representem esses processos;
* Utilizem esses dados para produzir informações gerenciais;
* Apoiem decisões com base em evidências.

---

## 2. CONCEITO CENTRAL DA DISCIPLINA

A disciplina está fundamentada na relação entre operações, dados e decisão, na qual os estudantes desenvolvem módulos de sistemas responsáveis pela geração de dados e, posteriormente, utilizam esses dados na construção de informações gerenciais para apoio à tomada de decisão.

Essa abordagem está alinhada aos eixos formativos do PPC do curso, com destaque para o Eixo de Tecnologia, ao envolver o desenvolvimento de soluções computacionais para registro, processamento e análise de dados, e para o Eixo de Formação Profissional, ao simular o uso de Sistemas de Informação em contextos organizacionais reais.

A disciplina adota uma perspectiva aplicada, baseada em casos reais de organizações, nos quais os estudantes atuam como analistas e desenvolvedores de soluções, reproduzindo práticas de mercado como:

* Desenvolvimento de sistemas de gestão (ERP simplificado);
* Integração de dados entre módulos organizacionais;
* Construção de dashboards e indicadores (Business Intelligence);
* Análise de desempenho e suporte à decisão.

Dessa forma, o estudante compreende, de maneira integrada, como os dados gerados nas operações organizacionais são transformados em informação estratégica, aproximando-se das demandas atuais do mercado de tecnologia e gestão orientada por dados.

---

## 3. ESTRUTURA DA DISCIPLINA

A disciplina será dividida em duas avaliações principais:

* **a) 1ª VA** - Desenvolvimento de um Sistema (ERP) e sua documentação
* **b) 2ª VA** - Desenvolvimento de um Sistema Gerencial (BI / Dashboard) e sua documentação

---

## 4. ORGANIZAÇÃO DO PROJETO

O desenvolvimento do projeto deverá simular um ambiente real de construção de Sistemas de Informação, no qual o estudante será responsável por:

* compreender o funcionamento organizacional do problema proposto;
* identificar processos, operações e fluxos de informação;
* modelar os dados necessários ao sistema;
* estruturar módulos integrados;
* implementar funcionalidades operacionais;
* consolidar informações financeiras;
* gerar dados para análise gerencial;
* construir indicadores e dashboards para apoio à tomada de decisão.

O aluno deverá desenvolver seu sistema de forma incremental ao longo da disciplina, acompanhando as etapas e entregáveis definidos nas avaliações.

O projeto desenvolvido deve obrigatoriamente:

* representar operações organizacionais reais;
* possuir integração entre módulos;
* garantir persistência e consistência dos dados;
* implementar regras de negócio compatíveis com o contexto do problema;
* gerar informações utilizáveis na camada analítica da 2ª VA.

A estrutura do projeto deve ser conforme o fluxo abaixo:

* **EMPRESA** - O aluno deverá escolher uma área de negócio para ser utilizado como base do projeto, definindo de forma geral sua área de atuação e suas principais atividades.
* **PROCESSOS DE NEGÓCIO** - A partir da área de negócio escolhida, o aluno deverá identificar os principais processos realizados e entender como as informações circulam entre essas atividades.
* **ERP** - O aluno deverá transformar esses processos em um ERP básico, desenvolvendo os módulos necessários para apoiar a operação da empresa e permitindo que as informações dos diferentes setores estejam integradas.
  * **COMPRAS** - O sistema deverá permitir registrar e acompanhar as operações relacionadas às compras da empresa, incluindo os produtos ou serviços adquiridos e seus fornecedores.
  * **VENDAS** - O sistema deverá permitir registrar as vendas realizadas pela empresa, relacionando clientes, produtos e valores e gerando as informações necessárias para os demais processos.
  * **ESTOQUE** - O sistema deverá controlar os produtos e suas movimentações, permitindo acompanhar as entradas, saídas e quantidades disponíveis em estoque.
  * **FINANCEIRO** - O sistema deverá registrar as movimentações financeiras decorrentes das operações da empresa, permitindo acompanhar, de forma básica, valores a pagar e a receber.
* **BANCO DE DADOS** - Todas as informações geradas pelos módulos do ERP deverão ser armazenadas de forma estruturada em um banco de dados, permitindo que os diferentes módulos compartilhem e utilizem essas informações.
* **BI** - Na segunda etapa do projeto, o aluno deverá utilizar os dados produzidos pelo ERP para realizar análises sobre o funcionamento e o desempenho da empresa.
* **INDICADORES** - A partir dos dados disponíveis, o aluno deverá definir indicadores relevantes para acompanhar os principais aspectos do negócio e responder às necessidades de informação da empresa.
* **DASHBOARD** - Os indicadores deverão ser apresentados em um dashboard que permita visualizar e analisar, de forma clara, as principais informações do negócio.
* **DECISÃO** - O objetivo final é que as informações produzidas pelo BI possam apoiar a tomada de decisões, permitindo ao gestor compreender melhor o desempenho da empresa e identificar situações que necessitem de atenção.

### 4.1 TECNOLOGIA OBRIGATÓRIA NA INFRAESTRUTURA DO PROJETO

Para garantir que todos os projetos possam ser executados, publicados e avaliados de forma padronizada, a infraestrutura tecnológica dos projetos deverá seguir uma arquitetura comum. Todos os alunos deverão desenvolver a aplicação utilizando **Python** e **Streamlit**, utilizar **PostgreSQL** como sistema gerenciador de banco de dados, hospedar o banco de dados no **Supabase**, utilizar autenticação por meio da **conta Google** e publicar a aplicação no **Streamlit Community Cloud**. A adoção dessa infraestrutura não limita a criatividade do aluno no desenvolvimento do sistema; ela estabelece apenas uma base tecnológica comum para todos os projetos.

* **Streamlit:** Será utilizado como tecnologia para desenvolvimento da interface web da aplicação, pois permite que os alunos desenvolvam sistemas funcionais utilizando Python, sem a necessidade de que cada projeto implemente separadamente uma arquitetura completa de frontend e backend. Dessa forma, o foco da disciplina permanece nos Sistemas de Informação, nos processos organizacionais, na modelagem dos dados, nas regras de negócio e na integração dos módulos do ERP, e não na construção de uma infraestrutura de software excessivamente complexa.
* **PostgreSQL:** Será o banco de dados obrigatório dos projetos e cada sistema deverá possuir uma estrutura de dados adequada ao funcionamento do ERP, contemplando as entidades, relacionamentos, restrições e informações necessárias aos processos definidos pelo aluno. O banco de dados não deverá ser utilizado apenas como local de armazenamento das informações das telas, ou seja, ele deverá representar adequadamente os processos e permitir a integração entre os diferentes módulos do sistema.
* **Supabase:** Será utilizado como ambiente de hospedagem e disponibilização do PostgreSQL. Com isso, cada aluno terá um banco de dados acessível pela aplicação publicada, permitindo que o ERP permaneça disponível mesmo quando o computador pessoal do aluno estiver desligado. Essa característica é importante para a avaliação, pois o professor poderá acessar o sistema e verificar seu funcionamento diretamente no ambiente publicado.
* **Autenticação Google:** Também será obrigatória e o acesso ao sistema deverá ser realizado por meio da conta institucional ou da conta Google definida para o projeto, permitindo que os sistemas tenham um mecanismo básico de identificação dos usuários. Além de aproximar o projeto de uma aplicação real, essa exigência permite trabalhar conceitos de autenticação, controle de acesso e segurança da informação.
* **Streamlit Community Cloud:** A aplicação deverá ser publicada no Streamlit Community Cloud e disponibilizada por meio de uma URL acessível pela Internet, pois essa exigência é particularmente importante porque o projeto não será considerado apenas um programa desenvolvido no computador do aluno.
* **GitHub:** O código-fonte do projeto deverá ser mantido em um repositório GitHub, associado à aplicação publicada pelo fato do objetivo não ser avaliar exclusivamente o domínio da ferramenta GitHub, mas estabelecer uma forma organizada de versionamento e disponibilização do código, pois permite acompanhar a evolução do projeto durante o semestre e facilita a manutenção e a publicação da aplicação no Streamlit Community Cloud.

---

## 5. ARQUITETURA OBRIGATÓRIA DO SISTEMA

A definição da arquitetura do sistema (organização de arquivos, camadas e módulos) será de responsabilidade de cada aluno que poderá adotar a estrutura que considerar mais adequada, desde que:

* O sistema esteja organizado de forma clara e compreensível;
* O sistema tenha separação mínima de responsabilidades (ex: dados, regras de negócio, interface);
* Os módulos do sistema estejam devidamente estruturados e integrados;
* O código permita manutenção e evolução.

---

## 6. AVALIAÇÃO 1ª VA – DESENVOLVIMENTO DO ERP E ENTREGA DO PROJETO

### OBJETIVO

O objetivo da 1ª VA é desenvolver um sistema de gestão, em escala reduzida, que represente processos centrais da organização, por meio da implementação de módulos integrados, permitindo a geração consistente de dados para uso gerencial posterior.

O sistema deverá:

* Permitir a entrada estruturada de dados, por meio de interfaces organizadas e consistentes;
* Implementar múltiplos módulos funcionais integrados, representando o fluxo de informação da organização;
* Possuir autenticação de usuários, garantindo controle de acesso ao sistema;
* Implementar regras de negócio compatíveis com o domínio do problema, evitando operações inconsistentes;
* Armazenar dados em banco relacional (PostgreSQL), garantindo integridade e relacionamento entre as entidades;
* Registrar operações transacionais com histórico e temporalidade (`timestamps`);
* Garantir que as operações realizadas em um módulo impactem outros módulos, simulando o funcionamento de um sistema real;
* Gerar uma base de dados coerente, consistente e suficiente para análises na 2ª VA.

### 9.1 DEFINIÇÃO DO MÓDULO DO SISTEMA

O aluno deverá desenvolver os módulos do sistema, obrigatoriamente integrados entre si e esses módulos devem representar o núcleo operacional da organização, garantindo:

* Geração de dados reais
* Fluxo de informação entre setores
* Suporte ao dashboard da 2ª VA

#### Módulos mínimos do projeto

| Módulo | Objetivo | Funcionalidades Esperadas | Integrações Obrigatórias |
| :--- | :--- | :--- | :--- |
| **Cadastro** | Gerenciar as entidades centrais necessárias ao funcionamento do sistema | Cadastro, edição, consulta e remoção de informações relacionadas às entidades do domínio do projeto | Deve servir como base para todos os demais módulos do sistema |
| **Compras** | Controlar aquisições, entradas de recursos, produtos, materiais ou insumos utilizados pela organização | Registro de compras, fornecedores, entradas, atualizações de disponibilidade e controle das aquisições realizadas | Deve impactar operações, disponibilidade de recursos e módulo financeiro |
| **Vendas** | Controlar as operações comerciais e geração de receitas da organização | Orçamentos, pedidos, vendas, faturamento, controle de clientes, emissão de comprovantes, histórico de vendas e acompanhamento | Deve consumir dados do cadastro, impactar estoque/operacional e gerar lançamentos automáticos no financeiro e analíticos |
| **Estoque** | Controlar movimentações e disponibilidade de produtos, materiais e insumos da organização | Controle de entradas, saídas, inventário, movimentações, disponibilidade, localização e atualização automática de estoque | Deve receber movimentações dos módulos de compras, vendas e operacional |
| **Operacional** | Representar a atividade principal da organização e os processos centrais executados no sistema | Execução das operações principais do projeto, registro das atividades organizacionais e processamento das operações do sistema | Deve consumir dados dos cadastros e gerar impactos financeiros e analíticos |
| **Financeiro** | Consolidar os impactos monetários gerados pelas operações do sistema | Contas a pagar, contas a receber, fluxo de caixa, receitas, despesas e movimentações financeiras | Deve receber informações dos módulos operacionais, vendas e de compras |
| **Business Intelligence (2ª VA)** | Transformar os dados operacionais em informações gerenciais para apoio à tomada de decisão | Indicadores (KPIs), dashboards, métricas, análises temporais e visualizações analíticas | Deve utilizar exclusivamente os dados gerados pelos demais módulos do sistema |
| **Autenticação e Controle de Acesso** | Garantir identificação dos usuários e controle de acesso às funcionalidades do sistema | Login, identificação do usuário autenticado, restrição de acesso e rastreabilidade das operações | Deve estar integrado a todos os módulos do sistema |
| **Integração entre Módulos** | Garantir o fluxo de informações entre os módulos do sistema | Compartilhamento de dados, impacto entre operações e sincronização das funcionalidades | Todos os módulos devem possuir integração operacional e compartilhamento consistente de dados |

### 9.2 FUNCIONALIDADES OBRIGATÓRIAS (CRUD E OPERAÇÕES INTEGRADAS)

#### 9.2.1 CRUD POR MÓDULO (OBRIGATÓRIO)
Cada entidade cadastral deverá possuir as operações de manutenção necessárias, enquanto os módulos operacionais deverão implementar as operações transacionais pertinentes ao contexto do projeto.

#### 9.2.2 OPERAÇÕES INTEGRADAS ENTRE MÓDULOS (OBRIGATÓRIO)
O sistema deverá implementar operações que representem o fluxo real de informação entre os módulos, de forma que ações em um módulo impactem diretamente outros.

#### 9.2.3 REGRAS DE NEGÓCIO (OBRIGATÓRIO)
As operações do sistema devem refletir regras compatíveis com o domínio do problema, garantindo consistência e coerência dos dados.

#### 9.2.4 CONSISTÊNCIA DOS DADOS
O sistema deve assegurar:
* Integridade entre os módulos
* Coerência das operações realizadas
* Persistência correta das informações

#### 9.2.5 REGISTRO DE DADOS PARA ANÁLISE
As operações implementadas devem gerar dados estruturados e utilizáveis para análise na 2ª VA.

#### 9.2.6 RESTRIÇÕES
Não será aceito:
* módulos isolados sem integração
* ausência de impacto entre operações
* inconsistência de dados
* funcionalidades que não representem o contexto do sistema

### 9.3 GERAÇÃO DE DADOS (CRÍTICO PARA 2ª VA)

O sistema deverá garantir o registro adequado das operações realizadas, de forma que os dados gerados possam ser utilizados posteriormente para análise na camada gerencial tendo um volume de dados suficiente para permitir análise temporal e comparativa (2ª VA). Para isso, todas as ações relevantes do sistema devem ser persistidas com informações suficientes para permitir rastreabilidade, consolidação e interpretação dos dados.

Cada operação realizada nos módulos do sistema deverá armazenar, obrigatoriamente, informações possibilitando a análise da evolução dos processos ao longo do tempo. Além disso, o sistema deve manter o histórico das transações realizadas, não sendo permitido substituir ou sobrescrever registros de forma que comprometa a análise posterior.

O registro das operações deve refletir o funcionamento real do sistema, contemplando eventos como movimentações, atendimentos, registros operacionais e demais interações relevantes e esses registros devem ser armazenados de forma estruturada no banco de dados, garantindo consistência e integração com os demais módulos.

Os dados gerados devem permitir sua utilização na construção de indicadores e análises na 2ª VA, sendo requisito que a estrutura de armazenamento possibilite agregações, comparações temporais e identificação de padrões, pois a ausência de registro adequado das operações comprometerá a análise gerencial e impactará diretamente a avaliação do sistema.

### 9.4 ENTREGÁVEIS DA 1ª VA

Cada aluno deverá apresentar e entregar um sistema de gestão funcional, acompanhado de documentação técnica que evidencie as decisões de modelagem, a estrutura do sistema e a integração entre os módulos desenvolvidos e deve demonstrar não apenas o funcionamento do sistema, mas também a coerência entre os módulos, a consistência dos dados e a aderência ao contexto do projeto proposto.

#### 9.4.1 SISTEMA FUNCIONAL
Deverá ser entregue um sistema implementado em Streamlit, plenamente operacional, contemplando:

* navegação estruturada entre as funcionalidades;
* implementação dos módulos definidos;
* execução das operações do sistema (cadastros e operações);
* integração entre os módulos;
* funcionamento sem erros críticos que impeçam o uso;

O sistema deve permitir a execução completa do fluxo proposto, evidenciando o funcionamento integrado dos módulos.

#### 9.4.2 DOCUMENTAÇÃO TÉCNICA
Cada aluno deve entregar um documento descrevendo o sistema desenvolvido, contemplando, no mínimo:

1. **Descrição do sistema**
   * contextualização do projeto;
   * objetivo do sistema;
   * escopo das funcionalidades implementadas;
2. **Descrição dos módulos**
   * identificação dos módulos desenvolvidos;
   * papel de cada módulo no sistema;
   * relação entre os módulos;
3. **Modelo de dados**
   * representação do modelo de dados (MER);
   * identificação das principais entidades e relacionamentos;
4. **Integração entre módulos**
   * descrição de como os módulos se conectam;
   * explicação das operações que envolvem mais de um módulo;
   * fluxo de dados entre as partes do sistema;
5. **Regras de negócio**
   * descrição das regras implementadas;
   * justificativa das validações e restrições adotadas;
   * relação com o contexto do problema;

### 9.5 RESUMO DOS ENTREGÁVEIS DA 1ª VA

#### Apresentação do Sistema

| Elemento | Descrição |
| :--- | :--- |
| **Sistema em execução** | Sistema desenvolvido em Streamlit, plenamente funcional |
| **Autenticação** | Login com Google implementado e funcional |
| **Navegação** | Estrutura de navegação entre os módulos do sistema |
| **Funcionalidades** | Execução de um fluxo completo do sistema envolvendo múltiplos módulos |
| **Integração** | Demonstração do fluxo entre os módulos |
| **Dados** | Utilização de dados reais gerados pelo sistema |

#### Documento Técnico

| Elemento | Descrição |
| :--- | :--- |
| **Descrição do sistema** | Contextualização, objetivo e escopo do sistema |
| **Módulos** | Descrição dos módulos implementados e suas funções |
| **Modelo de dados** | Representação (MER) das entidades e relacionamentos |
| **Integração** | Explicação do fluxo de dados entre os módulos |
| **Regras de negócio** | Descrição das regras implementadas no sistema |
| **Arquitetura** | Justificativa da estrutura adotada |

### 9.6 PONTUAÇÃO DA 1ª VA

| Critério | Descrição | Pontuação |
| :--- | :--- | :---: |
| **Sistema funcional e UX (Interface e usabilidade)** | Navegação, CRUD completo, execução do fluxo e funcionamento geral sem erros críticos | 3 |
| **Módulo financeiro** | Consolidação financeira coerente com as operações do sistema | 2 |
| **Banco de dados** | Modelagem, integridade e persistência dos dados | 1 |
| **Documentação técnica** | Clareza, descrição dos módulos, integração e regras de negócio | 2 |
| **Exercícios** | Exercícios 1 e 2 da disciplina | 2 |

---

## 10. AVALIAÇÃO DA 2ª VA – DASHBOARD (BUSINESS INTELLIGENCE)

### 10.1 OBJETIVO DA AVALIAÇÃO

Desenvolver uma camada de análise sobre o sistema construído na 1ª VA, utilizando os dados gerados pelos módulos operacionais para produzir informações gerenciais e apoio à tomada de decisão. Para isso, o sistema deverá:

* Utilizar os dados provenientes das operações da 1ª VA;
* Transformar dados em indicadores relevantes ao contexto do projeto;
* Permitir análise gerencial por meio de visualizações adequadas;
* Evidenciar a relação entre operações, dados e decisão.

### 10.2 DESENVOLVIMENTO DO MÓDULO ANALÍTICO

O sistema deverá incorporar um novo módulo destinado à análise de dados (dashboard), devidamente integrado aos módulos operacionais. Esse módulo deverá utilizar diferentes formas de visualização, como gráficos e indicadores numéricos, adequadas ao tipo de análise proposta, de modo a possibilitar a interpretação clara, consistente e orientada à tomada de decisão.

#### 10.2.1 Modelagem analítica
A modelagem analítica deve evidenciar a capacidade do sistema de transformar dados operacionais em informações relevantes, alinhadas ao contexto do projeto e às necessidades de análise, por meio da definição de indicadores coerentes com os processos implementados, da construção de consultas que permitam a extração, agregação e consolidação dos dados, e da organização das informações de forma adequada para análises temporais, comparativas e gerenciais, garantindo que os resultados apresentados reflitam efetivamente as operações do sistema e possibilitem interpretação consistente e apoio à tomada de decisão.

#### 10.2.2 Indicadores (KPIs)
O sistema deverá apresentar indicadores (KPIs), os quais devem refletir os problemas e objetivos do contexto do projeto, estar diretamente relacionados aos dados gerados na Avaliação 1 e permitir uma análise gerencial consistente, evidenciando o desempenho dos processos implementados, a identificação de padrões ou desvios e o suporte à tomada de decisão baseada em dados.

#### 10.2.3 Análise e interpretação (OBRIGATÓRIO)
O aluno deverá apresentar uma análise fundamentada nos dados gerados pelo sistema, contemplando a identificação de problemas, padrões ou tendências relevantes, a interpretação dos resultados obtidos a partir dos indicadores construídos e a proposição de ações ou melhorias coerentes com o contexto do projeto, demonstrando capacidade de transformar dados em informações úteis para apoio à tomada de decisão.

### 10.3 ENTREGÁVEIS

O aluno deverá apresentar e entregar a evolução do sistema desenvolvido na 1ª VA, incorporando a camada analítica (dashboard), bem como documentação que evidencie a construção dos indicadores, a análise dos dados e a capacidade de interpretação gerencial demonstrando a integração entre os módulos operacionais e o módulo analítico, evidenciando a transformação de dados em informação para apoio à tomada de decisão.

#### 10.3.1 Sistema com dashboard funcional
O sistema deverá apresentar um módulo de dashboard integrado, contemplando:

* visualização dos dados gerados na 1ª VA;
* implementação dos indicadores definidos;
* uso de gráficos e métricas para análise;
* navegação integrada com os demais módulos do sistema;
* funcionamento completo sem erros que impeçam a análise;

O dashboard deve estar conectado diretamente ao banco de dados do sistema, não sendo permitido uso de dados externos ou simulados.

#### 10.3.2 Indicadores implementados
O sistema deverá conter indicadores plenamente operacionais, incluindo:

* cálculo correto com base nos dados armazenados;
* atualização conforme os dados do sistema;
* coerência com o contexto do projeto;
* capacidade de representar o desempenho dos processos;

#### 10.3.3 Documentação técnica
O aluno deverá entregar um documento contendo a descrição e análise da camada analítica, incluindo:

1. **Descrição dos indicadores**
   * definição de cada indicador;
   * explicação do que mede;
   * relação com o contexto do sistema;
2. **Análise dos resultados**
   * interpretação dos dados apresentados;
   * identificação de problemas, padrões ou tendências;
   * relação entre os indicadores e o desempenho do sistema;
3. **Recomendações**
   * proposição de ações com base nos dados analisados;
   * sugestões de melhoria para o sistema ou processos;
   * justificativa das decisões propostas;

### 10.4 RESUMO DOS ENTREGÁVEIS DA 2ª VA

#### Apresentação do Dashboard

| Elemento | Descrição |
| :--- | :--- |
| **Dashboard funcional** | Módulo analítico integrado ao sistema da 1ª VA |
| **Integração de dados** | Uso exclusivo dos dados gerados na 1ª VA |
| **Indicadores** | KPIs implementados e operacionais |
| **Visualizações** | Uso de gráficos e métricas para análise |
| **Navegação** | Interface funcional e integrada ao sistema |
| **Análise** | Interpretação dos resultados apresentados |

#### Documento de Análise

| Elemento | Descrição |
| :--- | :--- |
| **Indicadores** | Descrição e definição dos KPIs utilizados |
| **Interpretação** | Explicação do que os indicadores representam |
| **Análise** | Interpretação dos resultados obtidos |
| **Problemas e padrões** | Identificação de comportamentos relevantes nos dados |
| **Recomendações** | Propostas de melhoria baseadas nos dados |

A avaliação considerará a qualidade da implementação, a integração entre os módulos, a consistência dos dados, a aderência ao contexto do projeto e a capacidade de análise apresentada.

### 9.8 PONTUAÇÃO DA 2ª VA

| Critério | Descrição | Pontos |
| :--- | :--- | :---: |
| **Dashboard funcional e UX (Visualização e usabilidade)** | Integração com o banco de dados, funcionamento correto e navegação entre as visualizações | 3 |
| **Indicadores (KPIs)** | Construção de indicadores coerentes com o sistema e cálculo correto com base nos dados | 2 |
| **Análise dos dados** | Interpretação dos resultados, identificação de padrões/problemas e proposição de melhorias | 1 |
| **Documentação analítica** | Descrição dos indicadores, análise realizada e recomendações propostas | 2 |
| **Exercício** | Exercício 3 da disciplina | 2 |